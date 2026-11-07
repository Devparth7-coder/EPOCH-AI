"""Module B — Research Planning Agent.

Turns claims into a non-redundant set of targeted searches. The planner is aware
of *why* a claim is time-sensitive: version, policy, numeric or temporal claims
get a different query shape than plain factual claims.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from app.core.config import settings
from app.services.llm.gateway import LLMGateway
from app.services.llm.prompts import RESEARCH_PLAN
from app.services.research import textutil as tu

QUERIES_PER_CLAIM = {"quick": 1, "standard": 2, "deep": 3}


def _core_phrase(claim: dict) -> str:
    text = claim["text"]
    # Keep entities and technical nouns; drop leading discourse markers.
    phrase = re.sub(r"^(According to [^,]+,|As of [^,]+,|In [^,]+,|It is|There are)\s*", "", text, flags=re.I)
    phrase = re.sub(r"\b(is|are|was|were|has been|have been|will be)\b", " ", phrase, flags=re.I)
    words = [w for w in re.findall(r"[A-Za-z0-9][\w.+#-]*", phrase) if w.lower() not in tu.STOPWORDS]
    return " ".join(words[:9]).strip() or tu.truncate(text, 60)


MONTH_TOKENS = set(tu.MONTHS)


def _entity_anchor(claim: dict) -> str:
    """Pick the subject of the claim: a proper noun, never a date or a number."""
    entities = [
        e for e in (claim.get("entities") or [])
        if e.lower() not in MONTH_TOKENS
        and not re.fullmatch(r"[\d.,%]+", e)
        and not re.fullmatch(r"(19|20)\d{2}", e)
    ]
    if entities:
        # Prefer the entity that opens the claim, then the longest one.
        first = claim["text"].split()[0].strip(",.")
        for entity in entities:
            if entity.split()[0] == first:
                return entity
        return max(entities, key=len)
    return _core_phrase(claim)


def plan_claim_queries(claim: dict, depth: str, year: int) -> list[str]:
    core = _core_phrase(claim)
    anchor = _entity_anchor(claim)
    ctype = claim.get("claim_type")
    queries: list[str] = []

    if ctype == "version":
        queries.append(f"{anchor} latest version documentation")
        queries.append(f"{anchor} release notes {year} deprecated")
    elif ctype == "policy":
        queries.append(f"{anchor} official policy updated {year}")
        queries.append(f"{core} current terms")
    elif ctype == "numeric":
        queries.append(f"{core} {year} official statistics")
        queries.append(f"{anchor} latest reported figure")
    elif ctype == "temporal":
        queries.append(f"{core} as of {year}")
        queries.append(f"{anchor} latest update")
    else:
        queries.append(core)
        queries.append(f"{anchor} official documentation")

    if depth == "deep":
        queries.append(f"{core} contradiction OR correction OR superseded")

    deduped: list[str] = []
    for q in queries:
        q = re.sub(r"\s+", " ", q).strip(" ?.")
        if q and q.lower() not in {d.lower() for d in deduped}:
            deduped.append(q)
    return deduped[: QUERIES_PER_CLAIM.get(depth, 2)]


def plan_research_heuristic(claims: list[dict], depth: str) -> list[dict]:
    year = datetime.now(timezone.utc).year
    seen: dict[str, str] = {}
    plans: list[dict] = []
    for claim in claims:
        queries = []
        needs = claim["checkworthiness"] >= 0.35
        for q in plan_claim_queries(claim, depth, year):
            key = q.lower()
            if key in seen and seen[key] != claim["text"]:
                continue  # avoid redundant searches across claims
            seen[key] = claim["text"]
            queries.append(q)
        plans.append(
            {
                "claim_text": claim["text"],
                "queries": queries,
                "needs_evidence": needs,
                "reason": (
                    "Time-sensitive claim requires current primary sources."
                    if claim["claim_type"] in {"version", "policy", "temporal", "numeric"}
                    else "Factual assertion requires corroboration."
                )
                if needs
                else "Low checkworthiness: opinions or hedged statements are not researched.",
            }
        )
    return plans


async def plan_research(claims: list[dict], depth: str, gw: LLMGateway) -> tuple[list[dict], dict]:
    if gw.live:
        claims_block = "\n".join(f"[{i}] {c['text']}" for i, c in enumerate(claims))
        result = await gw.complete_json(
            task="research_plan",
            system=RESEARCH_PLAN,
            user=f"Depth={depth}. Claims:\n{claims_block}\n\nReturn plans in claim order.",
            max_tokens=1200,
        )
        plans = result.data.get("plans") if isinstance(result.data, dict) else None
        if isinstance(plans, list) and len(plans) == len(claims):
            cleaned = []
            for claim, plan in zip(claims, plans):
                queries = [str(q).strip() for q in (plan.get("queries") or []) if str(q).strip()]
                if not queries:
                    queries = plan_claim_queries(claim, depth, datetime.now(timezone.utc).year)
                cleaned.append(
                    {
                        "claim_text": claim["text"],
                        "queries": queries[: QUERIES_PER_CLAIM.get(depth, 2) + 1],
                        "needs_evidence": bool(plan.get("needs_evidence", True)),
                        "reason": str(plan.get("reason", ""))[:400],
                    }
                )
            return cleaned, {
                "method": "llm",
                "model": result.model,
                "provider": result.provider,
                "latency_ms": result.latency_ms,
                "cost_usd": result.cost_usd,
            }
    return plan_research_heuristic(claims, depth), {
        "method": "heuristic",
        "model": "epoch-planner-v1",
        "provider": "deterministic",
    }
