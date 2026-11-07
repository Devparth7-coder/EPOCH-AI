"""Module E — Contradiction Detection Engine.

Two jobs:
  1. Classify the stance of each (claim, source) pair: supports / contradicts /
     context_only / supersedes.
  2. Separate *genuine contradictions* (same fact, incompatible value) from
     *context differences* (different scope, region, tier, time window). Real
     disagreements are preserved as unresolved rather than averaged away.
"""
from __future__ import annotations

import re

from app.core.config import settings
from app.services.llm.gateway import LLMGateway
from app.services.llm.prompts import STANCE
from app.services.research import textutil as tu
from app.services.research.temporal import parse_version_tuple, version_greater

SUPERSEDE_CUES = (
    "no longer", "end of life", "end-of-life", "superseded", "supersedes", "deprecated",
    "has been replaced", "replaced by", "reached end", "was withdrawn", "repealed", "phase out",
)
NEGATION_CUES = (
    "not ", "never", "isn't", "aren't", "wasn't", "doesn't", "didn't", "cannot", "false",
    "no longer", "without any", "will not", "has not", "have not", "is not", "are not",
    "deprecated", "withdrawn", "revoked", "unsupported", "not supported", "never shipped",
)
SCOPE_CUES = (
    "in the eu", "in india", "in the us", "for enterprise", "for free tier", "for students",
    "for hobby", "excluding", "except", "per region", "in some countries", "tier",
)
RELEVANCE_GATE = 0.45
CONFLICT_GATE = 0.34  # semantic conflicts require real topical overlap


def _sentences_for(text: str, claim: str, limit: int = 2) -> list[str]:
    sentences = tu.split_sentences(text) or [tu.truncate(text, 300)]
    ranked = sorted(sentences, key=lambda s: tu.coverage(claim, s), reverse=True)
    return [s for s in ranked[:limit] if tu.coverage(claim, s) > 0.12] or ranked[:1]


def _strip_dates(text: str) -> str:
    text = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", " ", text)
    text = re.sub(r"\b(?:19|20)\d{2}\b", " ", text)
    text = re.sub(r"\b(" + "|".join(tu.MONTHS) + r")\.?\s+\d{1,2},?", " ", text, flags=re.IGNORECASE)
    return text


def _unit_kind(token: str) -> str:
    low = token.lower()
    if low.endswith("%") or low.endswith("percent"):
        return "percent"
    if low.endswith(("million", "m")):
        return "scale_m"
    if low.endswith(("billion", "bn")):
        return "scale_b"
    if low.endswith(("thousand", "k")):
        return "scale_k"
    return "plain"


def _numeric_conflict(claim: dict, text: str) -> tuple[bool, str]:
    """Detect a genuine value disagreement, not a coincidental shared digit string.

    Rules (all must hold):
      * the claimed figure does NOT appear verbatim in the evidence passage, and
      * the evidence contains a figure of the same unit kind in the same topic
        context, and
      * the values differ by more than 2%.
    Dates are stripped first: they are the temporal engine's job.
    """
    claim_numbers = [
        n for n in tu.extract_numbers(_strip_dates(claim["text"])) if re.search(r"\d", n)
    ]
    claim_numbers = [n for n in claim_numbers if not re.fullmatch(r"(19|20)\d{2}", n)]
    if not claim_numbers:
        return False, ""
    # Bare integers are usually version numbers or enumerations and are handled
    # by the version/temporal engines. Only unit-bearing figures (%, currency,
    # magnitudes) or figures carrying an explicit measurement unit qualify here.
    claim_lower = claim["text"].lower()
    has_measure_unit = bool(
        re.search(
            r"\b(km|kg|kilometres?|kilometers?|metres?|meters?|miles?|mph|km/h|celsius|fahrenheit|°c|°f|"
            r"sq|hectares?|litres?|liters?|bytes?|gb|tb|mb|kb|ms|ns|hz|ghz|gbps|mbps|"
            r"tokens?|words?|parameters?|users?|customers?|employees?|people|persons?|students?|"
            r"seconds?|minutes?|hours?|days?|weeks?|months?|percent|percentage|"
            r"dollars?|euros?|rupees?|cents?|vcpus?|cores?|requests?|queries|qps|tps|ops)\b",
            claim_lower,
        )
    )
    claim_numbers = [
        n for n in claim_numbers if _unit_kind(n) != "plain" or has_measure_unit
    ]
    if not claim_numbers:
        return False, ""
    evidence_text = _strip_dates(text)
    evidence_numbers = tu.extract_numbers(evidence_text)
    if not evidence_numbers:
        return False, ""
    lowered = evidence_text.lower()

    def as_float(token: str) -> float | None:
        match = re.match(r"([\d,.]+)", token)
        if not match:
            return None
        try:
            value = float(match.group(1).replace(",", ""))
        except ValueError:
            return None
        kind = _unit_kind(token)
        return value * {"scale_m": 1e6, "scale_b": 1e9, "scale_k": 1e3}.get(kind, 1.0)

    for claimed in claim_numbers:
        # The claim's own figure being present means the evidence agrees.
        if claimed.lower() in lowered or claimed.rstrip("0").lower() in lowered:
            continue
        cv = as_float(claimed)
        if cv is None:
            continue
        for observed in evidence_numbers:
            if _unit_kind(observed) != _unit_kind(claimed):
                continue
            ov = as_float(observed)
            if ov is None or ov == 0:
                continue
            if abs(cv - ov) / max(abs(cv), abs(ov)) > 0.02:
                return True, f"claim says {claimed}, evidence says {observed}"
    return False, ""


CESSATION_CUES = (
    "no longer", "ended", "end of life", "superseded", "withdrawn", "deprecated", "revoked",
    "repealed", "phased out", "reached end", "was replaced", "has been replaced", "stopped",
)
DENIAL_CUES = (
    "never", "not supported", "is not", "are not", "was not", "were not", "does not", "do not",
    "did not", "cannot", "can't", "isn't", "aren't", "wasn't", "doesn't", "didn't", "without any",
    "will not", "has not", "have not", "false", "unsupported",
)


def polarity_kind(text: str) -> str | None:
    """Classify the negation style: 'cessation' (X ended) vs 'denial' (X never/not true)."""
    low = f" {text.lower()} "
    denial = [cue for cue in DENIAL_CUES if cue in low]
    cessation = [cue for cue in CESSATION_CUES if cue in low]
    if denial and not cessation:
        return "denial"
    if cessation and not denial:
        return "cessation"
    if denial and cessation:
        # "no longer supported" style: the denial is bounded by a cessation event.
        primary = min(low.find(cue) for cue in denial + cessation if cue in low)
        return "cessation" if any(low.find(c) == primary for c in cessation) else "denial"
    return None


def polarity_negative(text: str) -> bool:
    """True when the sentence asserts something is *not* the case."""
    return polarity_kind(text) is not None


def polarity_relation(claim_text: str, evidence_text: str) -> str | None:
    """Compare assertion polarity of claim and evidence.

    Only *directional* disagreements count:
      claim denies / evidence asserts        → contradicts
      claim neutral / evidence denies        → contradicts
      claim denies / evidence ends ("no longer") → contradicts (different denial style)
      same style on both sides               → supports
      claim neutral / evidence ends          → None (supersession logic decides)
    """
    ck = polarity_kind(claim_text)
    ek = polarity_kind(evidence_text)
    if ck and ek:
        return "supports" if ck == ek else "contradicts"
    if ck and not ek:
        return "contradicts"
    if not ck and ek == "denial":
        return "contradicts"
    return None


def anchored_versions(body_lower: str, versions, entity_words: set[str], radius: int = 80) -> set[str]:
    """Versions that appear within `radius` characters of one of the claim's subject words."""
    found: set[str] = set()
    for version in versions:
        for match in re.finditer(re.escape(version.lower()), body_lower):
            window = body_lower[max(0, match.start() - radius): match.end() + radius]
            if not entity_words or any(word in window for word in entity_words):
                found.add(version)
                break
    return found


def classify_pair_heuristic(claim: dict, source: dict, passage: str) -> dict:
    claim_text = claim["text"]
    body = f"{source.get('title', '')} {passage}"
    relevance = max(tu.coverage(claim_text, body), tu.overlap(claim_text, body))
    low_body = body.lower()
    has_supersede = any(cue in low_body for cue in SUPERSEDE_CUES)
    has_negation = any(cue in low_body for cue in NEGATION_CUES)
    scope_mismatch = any(cue in low_body for cue in SCOPE_CUES) and not any(
        cue in claim_text.lower() for cue in SCOPE_CUES
    )

    claim_versions = claim.get("versions") or [] or tu.extract_versions(claim_text)
    evidence_versions = tu.extract_versions(body)
    numeric_conflict, numeric_detail = _numeric_conflict(claim, body)

    stance = "context_only"
    strength = round(min(0.95, 0.35 + relevance * 0.6), 3)
    conflict_kind: str | None = None
    rationale = ""

    GENERIC_ENTITY_WORDS = {
        "release", "releases", "team", "teams", "report", "reports", "statement", "documentation",
        "official", "notes", "version", "versions", "current", "latest", "newest", "major", "stable",
    }
    entity_words = {
        word
        for entity in (claim.get("entities") or [])
        for word in re.findall(r"[a-z0-9][a-z0-9.+-]{2,}", str(entity).lower())
        if word not in GENERIC_ENTITY_WORDS and word not in tu.STOPWORDS
    }
    subject_match = (not entity_words) or any(word in low_body for word in entity_words)

    # A version only counts as evidence about *this* claim's subject when it appears
    # near the subject in the passage ("PostgreSQL 17 …", not "Django 5.1 runs on it").
    anchored_evidence_versions = anchored_versions(low_body, evidence_versions, entity_words)
    claim_version_set = {v.lower() for v in claim_versions}
    asserted_versions = claim_versions[:1]  # the version the claim is *about*
    newer_version = None
    for observed in anchored_evidence_versions:
        if observed.lower() in claim_version_set:
            continue  # the claim already names this version (e.g. "19 supersedes 18")
        for claimed in asserted_versions:
            if version_greater(observed, claimed):
                newer_version = (claimed, observed)

    if not subject_match:
        # A source about a different subject cannot confirm or refute this claim,
        # however many words happen to overlap.
        stance = "context_only"
        strength = round(min(relevance, 0.3), 3)
        rationale = "Source is about a different subject than the claim; kept as unrelated context."
    elif relevance < 0.2:
        stance = "context_only"
        strength = round(relevance, 3)
        rationale = "Low lexical overlap with the claim; retained as background only."
    elif newer_version:
        stance = "contradicts"
        conflict_kind = "version"
        strength = round(min(0.96, 0.6 + relevance * 0.35), 3)
        rationale = (
            f"Evidence references version {newer_version[1]} while the claim asserts "
            f"{newer_version[0]}; the claim's version is behind the current release."
        )
    elif polarity_relation(claim_text, body) == "supports" and relevance >= CONFLICT_GATE:
        # Both sides assert the same negative state ("no longer X"): agreement.
        stance = "supports"
        strength = round(min(0.92, 0.42 + relevance * 0.5), 3)
        rationale = "Evidence asserts the same negative state as the claim."
    elif polarity_relation(claim_text, body) == "contradicts":
        # One side asserts, the other denies, and the direction is unambiguous.
        stance = "contradicts"
        conflict_kind = "polarity"
        strength = round(min(0.95, 0.55 + relevance * 0.4), 3)
        rationale = (
            "Evidence asserts the opposite polarity to the claim "
            f"(claim={polarity_kind(claim_text)}, evidence={polarity_kind(body)})."
        )
    elif relevance < CONFLICT_GATE:
        stance = "context_only"
        rationale = (
            "Topically related but not specific enough to confirm or refute this claim; "
            "kept as context rather than treated as a conflict."
        )
    elif numeric_conflict:
        if scope_mismatch:
            stance = "context_only"
            conflict_kind = "scope"
            rationale = f"Different measurement scope ({numeric_detail}); not a genuine contradiction."
        else:
            stance = "contradicts"
            conflict_kind = "numeric"
            strength = round(min(0.95, 0.55 + relevance * 0.4), 3)
            rationale = f"Numeric disagreement: {numeric_detail}."
    elif has_supersede:
        # A supersession statement only contradicts the claim when the claim is
        # the thing being superseded. Check what the cue is actually about.
        cue_index = min((low_body.find(cue) for cue in SUPERSEDE_CUES if cue in low_body), default=0)
        # The *object* of a supersession follows the cue; only a little context
        # before it belongs to the statement being superseded.
        window = low_body[max(0, cue_index - 40): cue_index + 180]
        claim_terms = tu.token_set(claim_text)
        window_terms = tu.token_set(window)
        superseded_overlap = len(claim_terms & window_terms) / len(claim_terms) if claim_terms else 0.0
        # The claim's version counts as "the replacement" only when the evidence
        # explicitly frames it that way ("19 supersedes 18", "19 is the current …").
        window_versions = {v.lower() for v in tu.extract_versions(window)}
        claim_versions_lower = {v.lower() for v in claim_versions}
        claim_version_in_window = bool(claim_versions_lower & set(low_body.split())) or any(
            v in window for v in claim_versions_lower
        )
        other_version_in_window = bool(window_versions - claim_versions_lower)
        claim_version_is_the_replacement = (
            claim_version_in_window and other_version_in_window
        ) or any(
            re.search(
                rf"\b{re.escape(v)}\b[^.]{{0,90}}?(supersedes?|replaces?|is the current|current (major|stable|release|lts)|latest)",
                body,
                re.IGNORECASE,
            )
            for v in claim_versions
        ) if claim_versions else False

        if claim_version_is_the_replacement:
            stance = "supports"
            strength = round(min(0.92, 0.45 + relevance * 0.5), 3)
            rationale = (
                "Evidence confirms the claim's version as the current one while marking the older state as ended."
            )
        elif superseded_overlap >= 0.34:
            stance = "contradicts"
            conflict_kind = "superseded"
            strength = round(min(0.94, 0.5 + relevance * 0.4), 3)
            rationale = (
                "Evidence records that the exact state asserted by the claim has been replaced by a newer state."
            )
        elif superseded_overlap < 0.15:
            stance = "supports"
            strength = round(min(0.9, 0.42 + relevance * 0.5), 3)
            rationale = (
                "Evidence states the claimed fact and separately records a supersession of something else."
            )
        elif has_negation:
            stance = "contradicts"
            conflict_kind = "date"
            strength = round(min(0.94, 0.55 + relevance * 0.35), 3)
            rationale = "Evidence marks the claimed state as ended, replaced or superseded."
        else:
            stance = "supersedes"
            strength = round(min(0.9, 0.45 + relevance * 0.4), 3)
            rationale = "Evidence describes a newer state that partially supersedes the claim's frame of reference."
    elif relevance >= RELEVANCE_GATE:
        stance = "supports"
        strength = round(min(0.95, 0.4 + relevance * 0.55), 3)
        rationale = "Evidence states the same fact with compatible values and entities."
    else:
        stance = "context_only"
        rationale = "Partially related; insufficient to confirm or refute on its own."

    return {
        "claim_key": claim_text,
        "source_url": source["url"],
        "passage_text": passage,
        "stance": stance,
        "strength": strength,
        "rationale": rationale,
        "conflict_kind": conflict_kind,
        "relevance": round(relevance, 3),
    }


def _best_passage(claim: dict, source: dict) -> tuple[str, float]:
    content = source.get("content", "")
    sentences = _sentences_for(content, claim["text"])
    passage = " ".join(sentences)
    return passage, tu.coverage(claim["text"], passage)


def build_relationships_heuristic(claims: list[dict], sources: list[dict]) -> list[dict]:
    relationships: list[dict] = []
    for claim in claims:
        for source in sources:
            passage, relevance = _best_passage(claim, source)
            if relevance < 0.1:
                continue
            relationships.append(classify_pair_heuristic(claim, source, passage))
    return relationships


def _validate_llm(assessments: object, claims: list[dict], sources: list[dict]) -> list[dict]:
    if not isinstance(assessments, list):
        return []
    url_by_id = {s["url"]: s for s in sources}
    by_claim = {c["text"]: c for c in claims}
    valid_stances = {"supports", "contradicts", "context_only", "supersedes"}
    out: list[dict] = []
    for item in assessments:
        if not isinstance(item, dict):
            continue
        stance = str(item.get("stance", "")).lower()
        if stance not in valid_stances:
            continue
        claim_text = str(item.get("claim_text") or item.get("claim") or "").strip()
        url = str(item.get("source_url") or item.get("url") or "").strip()
        claim = by_claim.get(claim_text) or next(
            (c for c in claims if claim_text and claim_text[:40].lower() in c["text"].lower()), None
        )
        source = url_by_id.get(url)
        if not claim or not source:
            continue
        try:
            strength = float(item.get("strength", 0.6))
        except (TypeError, ValueError):
            strength = 0.6
        out.append(
            {
                "claim_key": claim["text"],
                "source_url": source["url"],
                "passage_text": str(item.get("rationale", ""))[:400],
                "stance": stance,
                "strength": round(max(0.0, min(1.0, strength)), 3),
                "rationale": str(item.get("rationale", ""))[:500],
                "conflict_kind": item.get("conflict_kind"),
                "relevance": round(strength, 3),
            }
        )
    return out


async def detect_relationships(
    claims: list[dict], sources: list[dict], gw: LLMGateway
) -> tuple[list[dict], dict]:
    heuristic = build_relationships_heuristic(claims, sources)
    if not gw.live or not claims or not sources:
        return heuristic, {"method": "heuristic", "pairs": len(heuristic), "provider": "deterministic"}

    blocks = []
    for claim in claims[: settings.research_max_claims]:
        for source in sources[:12]:
            passage, _ = _best_passage(claim, source)
            if not passage:
                continue
            from app.core.security import fence_untrusted

            blocks.append(
                f"CLAIM: {claim['text']}\nSOURCE_URL: {source['url']}\n"
                + fence_untrusted(f"{source['title']} ({source['domain']})", passage, max_chars=1200)
            )
    if not blocks:
        return heuristic, {"method": "heuristic", "pairs": len(heuristic), "provider": "deterministic"}

    result = await gw.complete_json(
        task="stance_detection",
        system=STANCE,
        user="Assess every pair below.\n\n" + "\n\n".join(blocks),
        max_tokens=2600,
    )
    llm_pairs = _validate_llm(result.data.get("assessments") if isinstance(result.data, dict) else None, claims, sources)
    if not llm_pairs:
        return heuristic, {"method": "heuristic", "pairs": len(heuristic), "provider": "deterministic", "llm_status": result.status}

    # LLM decisions win per (claim, source); heuristic fills the gaps.
    merged = {(p["claim_key"], p["source_url"]): p for p in heuristic}
    for pair in llm_pairs:
        merged[(pair["claim_key"], pair["source_url"])] = pair
    return list(merged.values()), {
        "method": "llm+heuristic",
        "pairs": len(merged),
        "llm_pairs": len(llm_pairs),
        "provider": result.provider,
        "model": result.model,
        "latency_ms": result.latency_ms,
        "cost_usd": result.cost_usd,
    }
