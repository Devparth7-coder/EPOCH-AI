"""Module A — Claim Extraction Engine.

Produces atomic, checkworthy claims with entities, dates, numbers and versions.
LLM path is used when a live provider is configured; the deterministic path runs
otherwise (tests, offline demos, benchmark reproducibility).
"""
from __future__ import annotations

import re

from app.core.config import settings
from app.core.logging import log
from app.schemas.enums import Verdict  # noqa: F401  (re-exported convenience)
from app.services.llm.gateway import LLMGateway
from app.services.llm.prompts import CLAIM_EXTRACTION
from app.services.research import textutil as tu

HEDGES = ("may", "might", "could", "possibly", "reportedly", "rumored", "might be", "some say", "i think")
OPINION = ("best", "worst", "beautiful", "amazing", "should", "ought", "in my opinion", "i believe")
AI_ANSWER_MARKERS = ("as an ai", "based on my knowledge", "as of my last update", "i cannot browse")


def _claim_type(text: str, versions: list[str], dates: list[str], numbers: list[str]) -> str:
    low = text.lower()
    if versions or re.search(r"\b(version|release|supports?|deprecat)", low):
        return "version"
    if re.search(r"\b(policy|terms|regulation|act|law|licen[cs]e|refund|gdpr|deadline|requirement)\b", low):
        return "policy"
    if dates or re.search(r"\b(current|currently|as of|latest|now|today|this year)\b", low):
        return "temporal"
    if numbers:
        return "numeric"
    return "factual"


def _checkworthiness(text: str, numbers: list[str], dates: list[str], versions: list[str]) -> float:
    score = 0.35
    if numbers:
        score += 0.2
    if dates:
        score += 0.15
    if versions:
        score += 0.15
    if re.search(r"\b(percent|%|billion|million|price|\$|€|₹)", text):
        score += 0.1
    if len(text.split()) > 6:
        score += 0.05
    low = text.lower()
    if any(h in low for h in HEDGES):
        score -= 0.2
    if any(o in low for o in OPINION):
        score -= 0.15
    return round(max(0.05, min(0.99, score)), 3)


def _is_extractable(sentence: str) -> bool:
    if sentence.endswith("?"):
        return False
    low = sentence.lower()
    # Opinions and judgements without any hard signal are not verifiable claims.
    if any(o in low for o in OPINION) and not re.search(r"\d", sentence):
        return False
    if any(m in low for m in AI_ANSWER_MARKERS):
        return False
    if len(sentence.split()) < 4:
        return False
    if not re.search(r"[a-zA-Z]{3,}", sentence):
        return False
    # Needs at least one factual signal or a plural/definite assertion.
    has_signal = bool(
        re.search(r"\d", sentence)
        or re.search(r"\b(is|are|was|were|has|have|supports?|requires?|allows?|costs?|uses?|became|remains)\b", low)
    )
    return has_signal


def _atomic_split(sentence: str) -> list[str]:
    """Split compound claims, but only when both halves stand alone."""
    pieces = re.split(r";\s+|\s+—\s+", sentence)
    expanded: list[str] = []
    for piece in pieces:
        if " and " in piece:
            left, right = piece.split(" and ", 1)
            # Both halves must stand on their own: a real subject (proper noun or
            # numeral) and enough words. Otherwise keep the sentence intact,
            # because a fragment like "is documented by the source" is not a claim.
            def _self_contained(fragment: str) -> bool:
                stripped = fragment.strip()
                # A claim fragment must open with its own subject (proper noun or
                # number); "was published on 7 October" is a predicate, not a claim.
                return len(stripped.split()) >= 4 and bool(re.match(r"[A-Z0-9]", stripped))

            if _self_contained(left) and _self_contained(right) and (
                re.search(r"\d", left) or re.search(r"\d", right)
            ):
                expanded.extend([left.strip(" ,.;"), right.strip(" ,.;")])
                continue
        expanded.append(piece.strip(" ,.;"))
    return [p for p in expanded if len(p.split()) >= 4]


def _build_claim(text: str, ordinal: int, parent: str | None = None) -> dict:
    numbers = tu.extract_numbers(text)
    dates = tu.extract_dates(text)
    versions = tu.extract_versions(text)
    entities = tu.extract_entities(text)
    return {
        "ordinal": ordinal,
        "text": text,
        "normalized": re.sub(r"\s+", " ", text.lower()).strip(" ."),
        "claim_type": _claim_type(text, versions, dates, numbers),
        "entities": entities,
        "numbers": numbers,
        "dates": dates,
        "versions": versions,
        "checkworthiness": _checkworthiness(text, numbers, dates, versions),
        "parent_claim_id": parent,
        "extracted_by": "heuristic/v1",
    }


def extract_claims_heuristic(text: str, limit: int | None = None) -> list[dict]:
    limit = limit or settings.research_max_claims
    sentences = tu.split_sentences(text)
    claims: list[dict] = []
    for sentence in sentences:
        if not _is_extractable(sentence):
            continue
        for piece in _atomic_split(sentence):
            if _is_extractable(piece):
                claims.append(_build_claim(piece, len(claims)))
        if len(claims) >= limit:
            break
    if not claims and text.strip():
        claims.append(_build_claim(tu.truncate(text, 400), 0))
    claims = claims[:limit]
    for i, claim in enumerate(claims):
        claim["ordinal"] = i
    return claims


def _validate_llm_claims(payload: object) -> list[dict]:
    if not isinstance(payload, dict):
        return []
    raw = payload.get("claims")
    if not isinstance(raw, list):
        return []
    allowed_types = {"factual", "numeric", "temporal", "version", "policy"}
    out: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "")).strip()
        if len(text) < 10:
            continue
        numbers = [str(n) for n in item.get("numbers", []) if str(n).strip()] or tu.extract_numbers(text)
        dates = [str(d) for d in item.get("dates", []) if str(d).strip()] or tu.extract_dates(text)
        versions = [str(v) for v in item.get("versions", []) if str(v).strip()] or tu.extract_versions(text)
        entities = [str(e) for e in item.get("entities", []) if str(e).strip()] or tu.extract_entities(text)
        ctype = str(item.get("claim_type", "")).lower()
        if ctype not in allowed_types:
            ctype = _claim_type(text, versions, dates, numbers)
        try:
            check = float(item.get("checkworthiness", 0.6))
        except (TypeError, ValueError):
            check = 0.6
        out.append(
            {
                "ordinal": len(out),
                "text": text,
                "normalized": re.sub(r"\s+", " ", text.lower()).strip(" ."),
                "claim_type": ctype,
                "entities": entities,
                "numbers": numbers,
                "dates": dates,
                "versions": versions,
                "checkworthiness": round(max(0.05, min(0.99, check)), 3),
                "parent_claim_id": None,
                "extracted_by": "llm",
            }
        )
    return out


async def extract_claims(text: str, gw: LLMGateway, limit: int | None = None) -> tuple[list[dict], dict]:
    """Return (claims, meta). Falls back to heuristics on any LLM failure."""
    limit = limit or settings.research_max_claims
    if gw.live:
        result = await gw.complete_json(
            task="claim_extraction",
            system=CLAIM_EXTRACTION,
            user=f"Extract at most {limit} atomic claims from this text:\n\n{text}",
            max_tokens=1800,
        )
        claims = _validate_llm_claims(result.data) if result.status == "ok" else []
        if claims:
            return claims[:limit], {
                "method": "llm",
                "provider": result.provider,
                "model": result.model,
                "route": result.route,
                "latency_ms": result.latency_ms,
                "tokens": result.prompt_tokens + result.completion_tokens,
                "cost_usd": result.cost_usd,
            }
        log.warning("claim_extraction_llm_fallback", extra={"event": "llm_fallback"})
    claims = extract_claims_heuristic(text, limit)
    return claims, {"method": "heuristic", "provider": "deterministic", "model": "epoch-heuristics-v1"}
