"""Module D — Temporal Intelligence Engine.

Responsibilities
----------------
* Separate *publication time* from *validity time* (effective_at).
* Score recency with claim-type-specific half-lives (a version claim decays far
  faster than a physical constant).
* Detect superseded sources, version drift, expired policies and claims that
  reference a date that has already been overtaken by newer evidence.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from app.services.research import textutil as tu

# Half-life in days per claim type: how fast the fact goes stale.
HALF_LIFE_DAYS = {
    "version": 210.0,
    "policy": 540.0,
    "numeric": 420.0,
    "temporal": 300.0,
    "factual": 1460.0,
}

SUPERSEDE_HINTS = (
    "supersede", "replaces", "no longer", "end of life", "end-of-life", "deprecated",
    "outdated", "sunset", "withdrawn", "amended", "repealed", "now available",
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def parse_version_tuple(version: str) -> tuple[int, ...]:
    nums = re.findall(r"\d+", version or "")
    return tuple(int(n) for n in nums[:4]) if nums else ()


def version_greater(a: str, b: str) -> bool:
    ta, tb = parse_version_tuple(a), parse_version_tuple(b)
    if not ta or not tb:
        return False
    length = max(len(ta), len(tb))
    ta = ta + (0,) * (length - len(ta))
    tb = tb + (0,) * (length - len(tb))
    return ta > tb


def recency_decay(age_days: float, claim_type: str) -> float:
    """Exponential decay in [0,1]; 1.0 means published today."""
    half_life = HALF_LIFE_DAYS.get(claim_type, 730.0)
    if age_days <= 0:
        return 1.0
    return round(0.5 ** (age_days / half_life), 4)


PRIMARY_TYPES = {"docs", "gov", "paper"}


def freshness_for_source(source: dict, claim_type: str, now: datetime | None = None) -> float:
    """Recency weight for a source.

    Fast-moving claims (versions, policies, statistics) decay quickly. Stable
    factual claims backed by primary documentation decay slowly with a floor:
    a spec does not stop being true because it is old, it stops being true when
    something supersedes it — which the supersession detector checks separately.
    """
    now = now or _now()
    published = source.get("published_at") or source.get("retrieved_at")
    if not isinstance(published, datetime):
        return 0.45  # unknown publication date: neutral-low prior
    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)
    age = tu.days_between(now, published)
    decay = recency_decay(age, claim_type)
    if claim_type == "factual" and source.get("source_type") in PRIMARY_TYPES:
        return round(max(decay, 0.62), 4)
    return decay


def _mentions_supersede(text: str) -> bool:
    low = text.lower()
    return any(hint in low for hint in SUPERSEDE_HINTS)


def analyze_temporal(
    claims: list[dict],
    sources: list[dict],
    relationships: list[dict],
    now: datetime | None = None,
) -> tuple[list[dict], dict[str, dict], dict[str, dict]]:
    """Return (observations, source_updates, per_claim_signals)."""
    now = now or _now()
    observations: list[dict] = []
    source_updates: dict[str, dict] = {}
    signals: dict[str, dict] = {}

    # ---- source-level freshness + supersession --------------------------
    for source in sources:
        claim_type = "factual"
        source["freshness_score"] = freshness_for_source(source, claim_type, now)
        published = source.get("published_at")
        age = tu.days_between(now, published) if isinstance(published, datetime) else None
        source_updates[source["url"]] = {"freshness_score": source["freshness_score"], "age_days": age}

    for claim in claims:
        ctype = claim.get("claim_type", "factual")
        # Only pairs with real topical overlap may influence a claim's temporal read.
        claim_pairs = [
            r for r in relationships
            if r["claim_key"] == claim["text"] and float(r.get("relevance", 0.0)) >= 0.3
        ]
        if not claim_pairs:
            claim_pairs = [r for r in relationships if r["claim_key"] == claim["text"]][:2]
        claim_sources = [s for s in sources if s["url"] in {r["source_url"] for r in claim_pairs}]
        claim_versions = set(tu.extract_versions(claim["text"]))

        fresh: list[float] = []
        ages: list[float] = []
        for source in claim_sources:
            src_type_best = ctype
            freshness = freshness_for_source(source, src_type_best, now)
            source_updates[source["url"]]["freshness_score"] = min(
                source_updates[source["url"]]["freshness_score"], freshness
            ) if source_updates[source["url"]]["freshness_score"] else freshness
            published = source.get("published_at")
            if isinstance(published, datetime):
                age = tu.days_between(now, published)
                ages.append(age)
                observations.append(
                    {
                        "claim_key": claim["text"],
                        "source_url": source["url"],
                        "observation_type": "recency",
                        "detail": (
                            f"Source published {published.date().isoformat()} "
                            f"({age:.0f} days before retrieval); recency weight "
                            f"{recency_decay(age, ctype):.2f} for a {ctype} claim."
                        ),
                        "published_at": published,
                        "effective_at": source.get("effective_at"),
                        "retrieved_at": source.get("retrieved_at"),
                        "age_days": round(age, 1),
                        "decay_factor": recency_decay(age, ctype),
                        "payload": {"claim_type": ctype},
                    }
                )
            fresh.append(freshness)
            if _mentions_supersede(source.get("content", "")):
                observations.append(
                    {
                        "claim_key": claim["text"],
                        "source_url": source["url"],
                        "observation_type": "superseded",
                        "detail": f"Source signals a supersession event: “{tu.truncate(source.get('content', ''), 180)}”",
                        "published_at": published,
                        "retrieved_at": source.get("retrieved_at"),
                        "payload": {"hint": True},
                    }
                )
            effective = source.get("effective_at")
            if isinstance(effective, datetime):
                kind = "future_effective" if effective > now else "effective_date"
                observations.append(
                    {
                        "claim_key": claim["text"],
                        "source_url": source["url"],
                        "observation_type": kind,
                        "detail": (
                            f"Effective {effective.date().isoformat()}, which is "
                            f"{'after' if effective > now else 'before'} the retrieval date "
                            f"{now.date().isoformat()}. Publication ≠ validity."
                        ),
                        "published_at": published,
                        "effective_at": effective,
                        "retrieved_at": source.get("retrieved_at"),
                        "payload": {},
                    }
                )

        # ---- version drift ------------------------------------------------
        anchors = {str(e).lower() for e in (claim.get("entities") or [])}
        evidence_versions: list[str] = []
        for pair in claim_pairs:
            passage_lower = str(pair.get("passage_text", "")).lower()
            # A version only counts if the passage is about the same subject.
            if anchors and not any(anchor in passage_lower for anchor in anchors):
                continue
            # Versions must be read from the passage that actually addresses the
            # claim, not from unrelated parts of the same document.
            evidence_versions.extend(tu.extract_versions(pair.get("passage_text", "")))
        for source in claim_sources:
            source_version = source.get("version")
            if not source_version:
                continue
            source_scope = f"{source.get('title', '')} {source.get('content', '')[:400]}".lower()
            if anchors and not any(anchor in source_scope for anchor in anchors):
                continue
            evidence_versions.append(str(source_version))
        newest_version = ""
        for candidate in evidence_versions:
            if not newest_version or version_greater(candidate, newest_version):
                newest_version = candidate
        version_drift = None
        if claim_versions and newest_version:
            claimed = max(claim_versions, key=lambda v: parse_version_tuple(v) or (0,))
            if version_greater(newest_version, claimed):
                version_drift = {"claimed": claimed, "current": newest_version}
                observations.append(
                    {
                        "claim_key": claim["text"],
                        "source_url": None,
                        "observation_type": "version_drift",
                        "detail": (
                            f"Claim references {claimed}, but retrieved evidence indicates "
                            f"{newest_version} is current."
                        ),
                        "payload": version_drift,
                    }
                )

        # ---- claim-side staleness ----------------------------------------
        claim_dates = [tu.parse_date(d) for d in claim.get("dates", [])]
        claim_dates = [d for d in claim_dates if d]
        reference_year = max((d.year for d in claim_dates), default=None)
        stale_reference = bool(reference_year and (now.year - reference_year) >= 1)
        newest_evidence_year = max(
            (s["published_at"].year for s in claim_sources if isinstance(s.get("published_at"), datetime)),
            default=None,
        )
        superseded_claim = bool(
            stale_reference and newest_evidence_year and newest_evidence_year > reference_year
        )
        if superseded_claim:
            observations.append(
                {
                    "claim_key": claim["text"],
                    "source_url": None,
                    "observation_type": "expired",
                    "detail": (
                        f"Claim is anchored to {reference_year}, while evidence published in "
                        f"{newest_evidence_year} is available. The claim's time reference has been overtaken."
                    ),
                    "payload": {"reference_year": reference_year, "newest_evidence_year": newest_evidence_year},
                }
            )

        signals[claim["text"]] = {
            "claim_type": ctype,
            "median_age_days": round(sorted(ages)[len(ages) // 2], 1) if ages else None,
            "min_age_days": round(min(ages), 1) if ages else None,
            "freshness": round(sum(fresh) / len(fresh), 4) if fresh else 0.0,
            "version_drift": version_drift,
            "reference_year": reference_year,
            "newest_evidence_year": newest_evidence_year,
            "stale_reference": stale_reference,
            "expired": superseded_claim,
            "has_effective_date": any(isinstance(s.get("effective_at"), datetime) for s in claim_sources),
            "observation_count": len([o for o in observations if o["claim_key"] == claim["text"]]),
        }

    return observations, source_updates, signals
