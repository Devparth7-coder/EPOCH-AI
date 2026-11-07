"""Benchmark results endpoint — serves measured numbers, never projections."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi import Depends

from app.core.ratelimit import rate_limit
from app.db.models import BenchmarkResult
from app.db.session import get_db

router = APIRouter(prefix="/benchmark", tags=["benchmark"], dependencies=[Depends(rate_limit)])

RESULTS = Path(__file__).resolve().parents[3] / "benchmark" / "results" / "latest.json"

METRIC_KEYS = [
    "accuracy", "macro_precision", "macro_recall", "macro_f1", "outdated_detection_recall",
    "citation_correctness", "evidence_coverage", "false_verification_rate",
    "mean_latency_ms", "cost_per_investigation_usd",
]


@router.get("/latest")
def latest(db: Session = Depends(get_db)):
    """Return the most recent benchmark artefact plus real example predictions."""
    if not RESULTS.exists():
        return {
            "available": False,
            "message": (
                "No benchmark artefact found. Run `python benchmark/run_benchmark.py` in /backend to "
                "produce measured results."
            ),
        }
    data = json.loads(RESULTS.read_text())
    examples = []
    wanted = {"VERIFIED", "OUTDATED", "CONFLICTING", "UNVERIFIED", "CONTRADICTED", "PARTIALLY_OUTDATED"}
    for pred in data.get("predictions", []):
        if pred["gold"] in wanted and pred.get("correct"):
            examples.append(
                {
                    "id": pred["id"],
                    "claim": pred["claim"],
                    "gold": pred["gold"],
                    "predicted": pred["predicted"],
                    "evidence_quality": pred["evidence_quality"],
                    "confidence": pred["confidence"],
                    "citations": pred["cited_urls"][:3],
                    "explanation": pred["explanation"][:400],
                }
            )
            wanted.discard(pred["gold"])
        if not wanted:
            break
    return {
        "available": True,
        "run_id": data["run_id"],
        "dataset_size": data["dataset_size"],
        "runtime_mode": data["runtime_mode"],
        "search_provider": data["search_provider"],
        "generated_at": data["generated_at"],
        "epoch": {k: data["epoch"].get(k) for k in METRIC_KEYS},
        "baseline": {k: data["baseline"].get(k) for k in METRIC_KEYS},
        "delta": data.get("delta", {}),
        "per_class": data["epoch"].get("per_class", {}),
        "confusion": data["epoch"].get("confusion", {}),
        "calibration": data.get("calibration"),
        "notes": data.get("notes", []),
        "examples": examples,
    }


@router.get("/history")
def benchmark_history(db: Session = Depends(get_db), limit: int = 10):
    rows = db.scalars(select(BenchmarkResult).order_by(BenchmarkResult.created_at.desc()).limit(limit)).all()
    return [
        {
            "id": r.id,
            "run_label": r.run_label,
            "system": r.system,
            "claim_count": r.claim_count,
            "runtime_mode": r.runtime_mode,
            "metrics": r.metrics,
            "created_at": r.created_at,
        }
        for r in rows
    ]
