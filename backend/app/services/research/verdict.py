"""Module F — Verdict Engine.

Deterministic, auditable rules over measured evidence. The engine refuses to say
VERIFIED without sufficient supporting evidence from credible, current sources.

Decision table (S = support quality, C = contradiction quality)
--------------------------------------------------------------
no usable evidence                      → UNVERIFIED
C dominant, no real support             → CONTRADICTED (or OUTDATED if temporal)
S and C both substantive, independent   → CONFLICTING (disagreement preserved)
S strong + supersession/drift detected  → OUTDATED / PARTIALLY_OUTDATED
S strong + fresh + corroborated         → VERIFIED
S weak/unreliable                       → UNVERIFIED
"""
from __future__ import annotations

from app.schemas.enums import Verdict
from app.services.research.scoring import calibrated_probability, compute_components

STRONG_SUPPORT = 0.45          # well corroborated
SUFFICIENT_SUPPORT = 0.33      # enough for a single authoritative primary source
MIN_SUPPORT_QUALITY = 0.30
STRONG_CONTRADICTION = 0.40
AUTHORITY_TRUST = 0.80


def _independent(components: dict) -> bool:
    return components["support_domains"] >= 2 or components["authority"] >= AUTHORITY_TRUST


def _latest(relationships: list[dict], sources_by_url: dict[str, dict]):
    dates = [
        sources_by_url.get(r["source_url"], {}).get("published_at")
        for r in relationships
    ]
    dates = [d for d in dates if d is not None]
    return max(dates) if dates else None


def _sufficient(components: dict) -> bool:
    return components["support_quality"] >= SUFFICIENT_SUPPORT and _independent(components)


def decide(
    *,
    claim: dict,
    relationships: list[dict],
    sources_by_url: dict[str, dict],
    temporal_signal: dict,
) -> dict:
    supporting = [r for r in relationships if r["stance"] == "supports"]
    contradicting = [r for r in relationships if r["stance"] == "contradicts"]
    superseding = [r for r in relationships if r["stance"] == "supersedes"]

    components = compute_components(
        supporting=supporting,
        contradicting=contradicting,
        sources_by_url=sources_by_url,
        temporal_signal=temporal_signal,
    )
    S = components["support_quality"]
    C = components["contradiction_quality"]
    drift = temporal_signal.get("version_drift")
    expired = bool(temporal_signal.get("expired"))
    temporal_change = bool(drift or expired)

    def latest(rels: list[dict]):
        dates = [sources_by_url.get(r["source_url"], {}).get("published_at") for r in rels]
        dates = [d for d in dates if d is not None]
        return max(dates) if dates else None

    support_date, contra_date = latest(supporting), latest(contradicting)
    years_newer = (
        (contra_date - support_date).days / 365.25
        if support_date is not None and contra_date is not None else 0.0
    )

    limitations: list[str] = []
    what_changed: str | None = None

    def note_change() -> None:
        nonlocal what_changed
        if drift:
            what_changed = f"Version moved from {drift['claimed']} to {drift['current']}."
        elif expired and temporal_signal.get("newest_evidence_year"):
            what_changed = (
                f"The fact was overtaken by a change published in {temporal_signal['newest_evidence_year']}."
            )
        elif contra_date is not None:
            what_changed = f"Newer evidence published {contra_date.date().isoformat()} states a different value."

    if not supporting and not contradicting and not superseding:
        verdict = Verdict.UNVERIFIED
        explanation = (
            "No retrieved source addresses this claim directly enough to confirm or refute it. "
            "EPOCH returns UNVERIFIED rather than guessing."
        )
        limitations.append("No directly relevant evidence was retrieved.")
    elif temporal_change and S >= SUFFICIENT_SUPPORT:
        # The claim's core survives, but a material part of it has been superseded.
        verdict = Verdict.PARTIALLY_OUTDATED
        note_change()
        explanation = (
            "Part of the claim still holds, but the temporal layer found a material change: "
            + (f"evidence now indicates {drift['current']} while the claim references {drift['claimed']}. "
               if drift else
               f"the claim is anchored to {temporal_signal.get('reference_year')} while evidence published in "
               f"{temporal_signal.get('newest_evidence_year')} is available. ")
            + "The surviving part is corroborated, so the claim is partially outdated rather than fully outdated."
        )
    elif temporal_change:
        verdict = Verdict.OUTDATED
        note_change()
        explanation = (
            "Credible, more recent evidence shows this claim described an earlier state that has since been "
            "superseded. "
            + (f"The claim references {drift['claimed']}; current evidence indicates {drift['current']}. "
               if drift else
               f"The claim's time reference ({temporal_signal.get('reference_year')}) has been overtaken by "
               f"evidence published in {temporal_signal.get('newest_evidence_year')}. ")
        ).strip()
        if S <= 0.05:
            limitations.append("No current source still supports the claim.")
    elif C >= STRONG_CONTRADICTION and S < STRONG_SUPPORT:
        temporally_resolved = years_newer >= 0.75 and S > 0.02
        if temporally_resolved:
            verdict = Verdict.OUTDATED
            note_change()
            explanation = (
                "The claim matches evidence that was current at the time it was published, but newer credible "
                f"evidence ({years_newer:.1f} years more recent) states a different value. The claim is outdated, "
                "not merely contradicted."
            )
        else:
            verdict = Verdict.CONTRADICTED
            kinds = sorted({r.get("conflict_kind") or "factual" for r in contradicting})
            explanation = (
                "Credible sources state an incompatible value: "
                + "; ".join(r["rationale"] for r in contradicting[:2])
                + f" (conflict type: {', '.join(kinds)})."
            )
    elif S >= STRONG_SUPPORT and C >= STRONG_CONTRADICTION and _independent(components):
        if temporal_change and years_newer >= 0.75:
            verdict = Verdict.OUTDATED
            note_change()
            explanation = (
                "Sources disagree, but the temporal layer resolves it: the evidence supporting the claim predates "
                f"the contradicting evidence by {years_newer:.1f} years and describes a state that has since changed."
            )
        else:
            verdict = Verdict.CONFLICTING
            explanation = (
                "Credible sources disagree. Supporting and contradicting evidence are both substantive and come "
                "from independent domains, and recency does not resolve the disagreement, so it is reported as "
                "unresolved rather than averaged away."
            )
            limitations.append("Sources conflict; no single authoritative resolution was found.")
    elif C >= STRONG_CONTRADICTION:
        kinds = sorted({r.get("conflict_kind") or "factual" for r in contradicting})
        verdict = Verdict.CONTRADICTED
        explanation = (
            "Credible sources state an incompatible value: "
            + "; ".join(r["rationale"] for r in contradicting[:2])
            + f" (conflict type: {', '.join(kinds)})."
        )
    elif superseding and S < 0.33:
        verdict = Verdict.OUTDATED
        note_change()
        explanation = (
            "The evidence set contains only a superseded description of this claim, plus a source that records a "
            "newer state. The claim is outdated."
        )
    elif superseding:
        verdict = Verdict.PARTIALLY_OUTDATED
        note_change()
        explanation = (
            "Evidence supports the substance of the claim but also records a newer state that partially "
            "supersedes it, so the claim is only partially current."
        )
    elif S >= SUFFICIENT_SUPPORT and _independent(components):
        verdict = Verdict.VERIFIED
        explanation = (
            f"{len(supporting)} source(s) across {components['support_domains']} independent domain(s) state the "
            "same fact with compatible values, and no credible source contradicts it."
        )
    elif S >= SUFFICIENT_SUPPORT or S >= STRONG_SUPPORT:
        verdict = Verdict.UNVERIFIED
        explanation = (
            "Evidence points the same way but is not independent or authoritative enough to certify the claim."
        )
        limitations.append("Support comes from a single, non-authoritative source.")
    elif S >= MIN_SUPPORT_QUALITY:
        verdict = Verdict.UNVERIFIED
        explanation = (
            "Some relevant evidence was found, but it is not strong, current or independent enough to certify "
            "the claim."
        )
        limitations.append("Support falls below the verification threshold.")
    else:
        verdict = Verdict.UNVERIFIED
        explanation = (
            "Retrieved evidence is related but does not directly confirm or refute the claim with sufficient quality."
        )
        limitations.append("Evidence quality below threshold.")

    if components["temporal"] < 0.4 and verdict in {Verdict.VERIFIED, Verdict.PARTIALLY_OUTDATED}:
        limitations.append("Supporting evidence is older than the claim's expected freshness window.")
    if components["support_domains"] <= 1 and verdict != Verdict.UNVERIFIED:
        limitations.append("Corroboration is limited to a single domain.")
    if temporal_signal.get("has_effective_date"):
        limitations.append("Effective dates differ from publication dates; validity was assessed against both.")
    if verdict == Verdict.UNVERIFIED and not limitations:
        limitations.append("Evidence quality below threshold.")

    limitations = list(dict.fromkeys(limitations))[:4]
    probability = calibrated_probability(components, verdict.value)

    return {
        "verdict": verdict.value,
        "calibrated_probability": probability,
        "evidence_quality": components["evidence_quality"],
        "supporting_count": len(supporting),
        "contradicting_count": len(contradicting),
        "components": {
            key: components[key]
            for key in (
                "authority", "relevance", "temporal", "corroboration", "consistency",
                "support_quality", "contradiction_quality", "support_domains", "contradiction_domains",
            )
        },
        "explanation": explanation,
        "what_changed": what_changed,
        "limitations": limitations,
        "decided_by": "verdict-engine/v2",
    }


def overall(verdicts: list[dict]) -> tuple[str, float]:
    """Aggregate claim verdicts into the session verdict (most severe wins)."""
    if not verdicts:
        return Verdict.UNVERIFIED.value, 0.0
    severity = {
        Verdict.VERIFIED.value: 0,
        Verdict.PARTIALLY_OUTDATED.value: 1,
        Verdict.CONFLICTING.value: 2,
        Verdict.UNVERIFIED.value: 2,
        Verdict.OUTDATED.value: 3,
        Verdict.CONTRADICTED.value: 3,
    }
    worst = max(verdicts, key=lambda v: (severity.get(v["verdict"], 2), -v["evidence_quality"]))
    counts: dict[str, int] = {}
    for v in verdicts:
        counts[v["verdict"]] = counts.get(v["verdict"], 0) + 1
    top_count = max(counts.values())
    if top_count / len(verdicts) >= 0.66:
        winner = max(counts, key=counts.get)
    else:
        winner = worst["verdict"]
    confidence = round(sum(v["calibrated_probability"] for v in verdicts) / len(verdicts), 4)
    return winner, confidence
