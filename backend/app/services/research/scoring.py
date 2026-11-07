"""Module G — Confidence & Evidence Scoring.

Evidence quality (0–1) is a *measurement*: how good is the evidence we hold?
Calibrated probability is a *prediction*: how likely is the verdict correct?
They are computed separately and never conflated in the UI.

    quality = 0.30·authority + 0.22·relevance + 0.20·temporal
            + 0.18·corroboration + 0.10·(1 − contradiction_penalty)
"""
from __future__ import annotations

import json
import math
from pathlib import Path

WEIGHTS = {
    "authority": 0.30,
    "relevance": 0.22,
    "temporal": 0.20,
    "corroboration": 0.18,
    "consistency": 0.10,
}

CALIBRATION_PATH = Path(__file__).with_name("calibration.json")
# Default Platt-style coefficients (identity-ish); replaced by benchmark fitting.
DEFAULT_CALIBRATION = {"a": -0.35, "b": 2.9, "c": 1.4, "trained_on": "default-prior", "n": 0}


def load_calibration() -> dict:
    if CALIBRATION_PATH.exists():
        try:
            data = json.loads(CALIBRATION_PATH.read_text())
            if {"a", "b", "c"} <= set(data):
                return data
        except json.JSONDecodeError:
            pass
    return DEFAULT_CALIBRATION


def save_calibration(payload: dict) -> None:
    CALIBRATION_PATH.write_text(json.dumps(payload, indent=2))


def compute_components(
    *,
    supporting: list[dict],
    contradicting: list[dict],
    sources_by_url: dict[str, dict],
    temporal_signal: dict,
) -> dict[str, float]:
    def domain(rel: dict) -> str:
        return sources_by_url.get(rel["source_url"], {}).get("domain", "unknown")

    def quality(rels: list[dict]) -> float:
        if not rels:
            return 0.0
        total = 0.0
        for rel in rels:
            source = sources_by_url.get(rel["source_url"], {})
            total += (
                rel["strength"]
                * float(source.get("authority_score", 0.5))
                * max(0.3, float(source.get("freshness_score", 0.5)))
            )
        # Saturating aggregate: 3 strong independent sources ≈ 1.0
        return round(1 - math.exp(-1.1 * total), 4)

    support_q = quality(supporting)
    contra_q = quality(contradicting)

    authority = (
        sum(float(sources_by_url.get(r["source_url"], {}).get("authority_score", 0)) for r in supporting + contradicting)
        / max(1, len(supporting) + len(contradicting))
    )
    relevance = (
        sum(float(r.get("relevance", r["strength"])) for r in supporting + contradicting)
        / max(1, len(supporting) + len(contradicting))
    )
    temporal = float(temporal_signal.get("freshness", 0.0))
    support_domains = {domain(r) for r in supporting}
    contra_domains = {domain(r) for r in contradicting}
    independent = len(support_domains - contra_domains)
    corroboration = round(min(1.0, independent / 3.0), 4)
    consistency = round(max(0.0, 1.0 - contra_q / (support_q + contra_q + 1e-6)), 4)

    quality_total = (
        WEIGHTS["authority"] * authority
        + WEIGHTS["relevance"] * relevance
        + WEIGHTS["temporal"] * temporal
        + WEIGHTS["corroboration"] * corroboration
        + WEIGHTS["consistency"] * consistency
    )

    return {
        "authority": round(authority, 4),
        "relevance": round(relevance, 4),
        "temporal": round(temporal, 4),
        "corroboration": corroboration,
        "consistency": consistency,
        "support_quality": support_q,
        "contradiction_quality": contra_q,
        "support_domains": len(support_domains),
        "contradiction_domains": len(contra_domains),
        "evidence_quality": round(quality_total, 4),
    }


def calibrated_probability(components: dict, verdict: str) -> float:
    """Map evidence features → probability that the chosen verdict is correct.

    Calibrated on the labelled benchmark (`backend/benchmark/run_benchmark.py
    --fit-calibration`); falls back to documented priors until then.
    """
    cal = load_calibration()
    support = components.get("support_quality", 0.0)
    contra = components.get("contradiction_quality", 0.0)
    quality = components.get("evidence_quality", 0.0)
    z = cal["a"] + cal["b"] * support + cal["c"] * contra + 1.1 * quality - 0.6
    if verdict == "UNVERIFIED":
        # UNVERIFIED is a refusal to determine, not a finding. Reporting a high
        # number here would be dishonest, so it is capped below a coin flip.
        return round(min(0.5, 0.15 + 0.35 * (1.0 - quality)), 4)
    base = 1 / (1 + math.exp(-z))
    prior = {
        "VERIFIED": 0.62, "OUTDATED": 0.7, "PARTIALLY_OUTDATED": 0.58, "CONTRADICTED": 0.68,
        "CONFLICTING": 0.5, "UNVERIFIED": 0.32,
    }.get(verdict, 0.5)
    return round(max(0.05, min(0.97, 0.55 * base + 0.45 * prior)), 4)
