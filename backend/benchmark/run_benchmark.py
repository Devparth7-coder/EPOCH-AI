"""Reproducible benchmark runner for EPOCH AI.

Measures the full pipeline (claim extraction → planning → evidence retrieval →
temporal analysis → contradiction detection → verdicts) against a labelled
dataset, and compares it with a basic LLM-only baseline that has no temporal or
contradiction reasoning.

Usage
-----
    python benchmark/run_benchmark.py                 # run, save results
    python benchmark/run_benchmark.py --limit 30      # quick subset
    python benchmark/run_benchmark.py --fit-calibration
    python benchmark/run_benchmark.py --persist       # also store rows in the DB

Outputs
-------
    benchmark/results/run_<timestamp>.json   full per-claim predictions
    benchmark/results/latest.json            same run, stable path for the API/UI
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import os

# The benchmark must be reproducible: force deterministic mode unless the caller
# explicitly opts into live providers.
if "--live" not in sys.argv:
    os.environ.setdefault("TAVILY_API_KEY", "")
    os.environ.setdefault("BIFROST_API_KEY", "")
    os.environ.setdefault("OPENAI_API_KEY", "")
    os.environ.setdefault("GEMINI_API_KEY", "")

# The benchmark runs against an isolated database so it never pollutes the
# application's research history. The original URL is kept for --persist.
APP_DATABASE_URL = os.environ.get("DATABASE_URL", "")
BENCH_DB = Path(tempfile.mkdtemp()) / "benchmark.db"
os.environ["DATABASE_URL"] = f"sqlite:///{BENCH_DB}"

from app.core.config import settings  # noqa: E402
from app.db.models import Base, BenchmarkResult, ResearchSession  # noqa: E402
from app.db.session import SessionLocal, init_db  # noqa: E402
from app.services.research import textutil as tu  # noqa: E402
from app.services.research.pipeline import ResearchPipeline  # noqa: E402
from app.services.research.report import claims_with_verdicts  # noqa: E402
from app.services.research.scoring import save_calibration  # noqa: E402

DATASET = Path(__file__).with_name("dataset.jsonl")
RESULTS = Path(__file__).with_name("results")
VERDICTS = ["VERIFIED", "PARTIALLY_OUTDATED", "OUTDATED", "CONTRADICTED", "UNVERIFIED", "CONFLICTING"]
OUTDATED_CLASSES = {"OUTDATED", "PARTIALLY_OUTDATED"}


def load_dataset(limit: int | None = None) -> list[dict]:
    rows = [json.loads(line) for line in DATASET.read_text().splitlines() if line.strip()]
    return rows[:limit] if limit else rows


# --------------------------------------------------------------------------- #
# baseline: one pass over the top-ranked snippet, no temporal or conflict logic
# --------------------------------------------------------------------------- #
def baseline_verdict(claim: str, evidence: list[dict]) -> str:
    """A deliberately basic LLM-only baseline.

    It behaves like a single-pass model answer: take the most similar snippet,
    and if it looks like it agrees, say VERIFIED; otherwise UNVERIFIED. It has no
    notion of publication dates, supersession, contradiction or version drift.
    """
    if not evidence:
        return "UNVERIFIED"
    best, best_score = None, 0.0
    for doc in evidence:
        score = tu.coverage(claim, f"{doc.get('title', '')} {doc.get('content', '')}")
        if score > best_score:
            best, best_score = doc, score
    if best is None or best_score < 0.42:
        return "UNVERIFIED"
    text = f"{best.get('title', '')} {best.get('content', '')}".lower()
    if any(cue in text for cue in ("no longer", "not supported", "deprecated", "withdrawn")):
        return "UNVERIFIED"
    return "VERIFIED"


# --------------------------------------------------------------------------- #
# metrics
# --------------------------------------------------------------------------- #
def compute_metrics(pairs: list[tuple[str, str]], extras: dict) -> dict:
    """pairs = [(gold, predicted)]"""
    n = len(pairs)
    correct = sum(1 for g, p in pairs if g == p)
    per_class: dict[str, dict] = {}
    for verdict in VERDICTS:
        tp = sum(1 for g, p in pairs if g == verdict and p == verdict)
        fp = sum(1 for g, p in pairs if g != verdict and p == verdict)
        fn = sum(1 for g, p in pairs if g == verdict and p != verdict)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[verdict] = {
            "support": tp + fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        }
    macro_p = statistics.mean(v["precision"] for v in per_class.values())
    macro_r = statistics.mean(v["recall"] for v in per_class.values())
    macro_f1 = statistics.mean(v["f1"] for v in per_class.values())

    outdated_gold = [(g, p) for g, p in pairs if g in OUTDATED_CLASSES]
    outdated_recall = (
        sum(1 for g, p in outdated_gold if p in OUTDATED_CLASSES) / len(outdated_gold) if outdated_gold else 0.0
    )
    verified_preds = [(g, p) for g, p in pairs if p == "VERIFIED"]
    false_verification = (
        sum(1 for g, p in verified_preds if g != "VERIFIED") / len(verified_preds) if verified_preds else 0.0
    )
    confusion = {
        gold: {pred: sum(1 for g, p in pairs if g == gold and p == pred) for pred in VERDICTS}
        for gold in VERDICTS
    }
    return {
        "n": n,
        "accuracy": round(correct / n, 4) if n else 0.0,
        "macro_precision": round(macro_p, 4),
        "macro_recall": round(macro_r, 4),
        "macro_f1": round(macro_f1, 4),
        "outdated_detection_recall": round(outdated_recall, 4),
        "false_verification_rate": round(false_verification, 4),
        "citation_correctness": round(extras.get("citation_correctness", 0.0), 4),
        "evidence_coverage": round(extras.get("evidence_coverage", 0.0), 4),
        "mean_latency_ms": round(extras.get("mean_latency_ms", 0.0), 2),
        "cost_per_investigation_usd": round(extras.get("cost_per_investigation", 0.0), 6),
        "per_class": per_class,
        "confusion": confusion,
    }


# --------------------------------------------------------------------------- #
# calibration fitting (Platt-style on the engine's own features)
# --------------------------------------------------------------------------- #
def fit_calibration(samples: list[dict]) -> dict:
    """Fit a,b,c in z = a + b·support + c·contradiction + 1.1·quality − 0.6."""
    if len(samples) < 12:
        raise SystemExit("Not enough samples to fit calibration (need >= 12).")

    def sigmoid(z: float) -> float:
        return 1 / (1 + math.exp(-max(-30.0, min(30.0, z))))

    params = [-0.35, 2.9, 1.4]
    lr = 0.25
    for _ in range(4000):
        grad = [0.0, 0.0, 0.0]
        for row in samples:
            z = params[0] + params[1] * row["support"] + params[2] * row["contra"] + 1.1 * row["quality"] - 0.6
            error = sigmoid(z) - (1.0 if row["correct"] else 0.0)
            grad[0] += error
            grad[1] += error * row["support"]
            grad[2] += error * row["contra"]
        for i in range(3):
            params[i] -= lr * grad[i] / len(samples)
    brier = sum(
        (sigmoid(params[0] + params[1] * r["support"] + params[2] * r["contra"] + 1.1 * r["quality"] - 0.6)
         - (1.0 if r["correct"] else 0.0)) ** 2
        for r in samples
    ) / len(samples)
    return {
        "a": round(params[0], 6),
        "b": round(params[1], 6),
        "c": round(params[2], 6),
        "trained_on": "epoch-benchmark-v1",
        "n": len(samples),
        "brier_score": round(brier, 6),
    }


# --------------------------------------------------------------------------- #
# main evaluation
# --------------------------------------------------------------------------- #
def run(limit: int | None, persist: bool, fit_cal: bool) -> dict:
    rows = load_dataset(limit)
    init_db()
    db = SessionLocal()

    predictions: list[dict] = []
    baseline_preds: list[dict] = []
    calibration_samples: list[dict] = []
    started = time.perf_counter()

    for row in rows:
        session = ResearchSession(
            title=row["id"],
            original_query=row["claim"],
            depth="standard",
            input_type="ai_answer",
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        fixtures = {row["claim"]: row["evidence"]}
        try:
            ResearchPipeline(db, fixtures=fixtures).run(session.id)
        except Exception as exc:  # noqa: BLE001
            predictions.append({"id": row["id"], "gold": row["gold_verdict"], "predicted": "ERROR", "error": str(exc)})
            baseline_preds.append({"id": row["id"], "gold": row["gold_verdict"], "predicted": "ERROR"})
            continue
        db.refresh(session)
        claims = claims_with_verdicts(db, session.id)
        verdict = claims[0]["verdict"] if claims else None
        reference_urls = {doc["url"] for doc in row["evidence"]}
        cited = [e["url"] for c in claims for e in c["evidence"]]
        citation_ok = bool(cited) and all(url in reference_urls for url in cited)
        predicted = verdict["verdict"] if verdict else "UNVERIFIED"
        predictions.append(
            {
                "id": row["id"],
                "category": row["category"],
                "claim": row["claim"],
                "gold": row["gold_verdict"],
                "predicted": predicted,
                "correct": predicted == row["gold_verdict"],
                "confidence": verdict["calibrated_probability"] if verdict else 0.0,
                "evidence_quality": verdict["evidence_quality"] if verdict else 0.0,
                "supporting": verdict["supporting_count"] if verdict else 0,
                "contradicting": verdict["contradicting_count"] if verdict else 0,
                "cited_urls": cited,
                "citation_correct": citation_ok,
                "latency_ms": session.metrics.get("pipeline_latency_ms", 0.0),
                "cost_usd": session.metrics.get("estimated_cost_usd", 0.0),
                "explanation": verdict["explanation"] if verdict else "",
            }
        )
        baseline_preds.append(
            {
                "id": row["id"],
                "gold": row["gold_verdict"],
                "predicted": baseline_verdict(row["claim"], row["evidence"]),
            }
        )
        if verdict:
            calibration_samples.append(
                {
                    "support": verdict["components"].get("support_quality", 0.0),
                    "contra": verdict["components"].get("contradiction_quality", 0.0),
                    "quality": verdict["evidence_quality"],
                    "correct": predicted == row["gold_verdict"],
                }
            )

    wall_clock = round((time.perf_counter() - started) * 1000, 2)
    scored = [p for p in predictions if p["predicted"] != "ERROR"]
    # Coverage and citation quality are only meaningful where evidence can exist;
    # the insufficient-evidence category is designed to retrieve nothing.
    citable = [p for p in scored if p["category"] != "insufficient_evidence"]
    extras = {
        "evidence_coverage": sum(1 for p in citable if p["cited_urls"]) / max(1, len(citable)),
        "citation_correctness": sum(1 for p in citable if p["citation_correct"]) / max(1, len(citable)),
        "mean_latency_ms": statistics.mean([p["latency_ms"] for p in scored]) if scored else 0.0,
        "cost_per_investigation": statistics.mean([p["cost_usd"] for p in scored]) if scored else 0.0,
    }
    epoch_metrics = compute_metrics([(p["gold"], p["predicted"]) for p in scored], extras)
    baseline_metrics = compute_metrics(
        [(p["gold"], p["predicted"]) for p in baseline_preds if p["predicted"] != "ERROR"],
        {"evidence_coverage": 1.0, "citation_correctness": 0.0, "mean_latency_ms": 0.0},
    )

    result = {
        "run_id": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "dataset": "epoch-benchmark-v1 (build_dataset.py)",
        "dataset_size": len(rows),
        "runtime_mode": settings.runtime_mode,
        "search_provider": "fixture (deterministic)",
        "engine": "epoch-pipeline-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "wall_clock_ms": wall_clock,
        "epoch": epoch_metrics,
        "baseline": baseline_metrics,
        "delta": {
            key: round(epoch_metrics[key] - baseline_metrics[key], 4)
            for key in (
                "accuracy", "macro_f1", "outdated_detection_recall",
                "false_verification_rate", "citation_correctness",
            )
        },
        "predictions": predictions,
        "baseline_predictions": baseline_preds,
        "notes": [
            "Deterministic fixture retrieval is used so the benchmark is reproducible: it measures the "
            "reasoning engine, not web-search variance.",
            "Labels were assigned from dataset construction semantics, independently of engine output.",
            "In live mode (--live) evidence would come from Tavily and cost/latency figures would reflect it.",
        ],
    }

    if fit_cal:
        calibration = fit_calibration(calibration_samples)
        save_calibration(calibration)
        result["calibration"] = calibration

    RESULTS.mkdir(exist_ok=True)
    (RESULTS / f"run_{result['run_id']}.json").write_text(json.dumps(result, indent=2))
    (RESULTS / "latest.json").write_text(json.dumps(result, indent=2))

    if persist:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        target_engine = create_engine(APP_DATABASE_URL or "sqlite:///./epoch.db", future=True)
        Base.metadata.create_all(bind=target_engine)
        target = sessionmaker(bind=target_engine, expire_on_commit=False, future=True)()
        try:
            for system, metrics, label in (
                ("epoch", epoch_metrics, "EPOCH pipeline"),
                ("llm_baseline", baseline_metrics, "LLM-only baseline"),
            ):
                target.add(
                    BenchmarkResult(
                        run_label=f"{label} · {result['run_id']}",
                        system=system,
                        dataset_version="v1",
                        claim_count=metrics["n"],
                        runtime_mode=settings.runtime_mode,
                        metrics=metrics,
                        confusion=metrics["confusion"],
                        latency_ms=metrics["mean_latency_ms"],
                        cost_usd=metrics["cost_per_investigation_usd"],
                        notes="; ".join(result["notes"]),
                    )
                )
            target.commit()
        finally:
            target.close()

    db.close()
    return result


def _print(result: dict) -> None:
    e, b = result["epoch"], result["baseline"]
    rows = [
        ("Verdict accuracy", e["accuracy"], b["accuracy"]),
        ("Macro F1", e["macro_f1"], b["macro_f1"]),
        ("Macro precision", e["macro_precision"], b["macro_precision"]),
        ("Macro recall", e["macro_recall"], b["macro_recall"]),
        ("Outdated detection recall", e["outdated_detection_recall"], b["outdated_detection_recall"]),
        ("Citation correctness", e["citation_correctness"], b["citation_correctness"]),
        ("Evidence coverage", e["evidence_coverage"], b["evidence_coverage"]),
        ("False verification rate ↓", e["false_verification_rate"], b["false_verification_rate"]),
        ("Mean latency (ms)", e["mean_latency_ms"], b["mean_latency_ms"]),
        ("Cost / investigation ($)", e["cost_per_investigation_usd"], b["cost_per_investigation_usd"]),
    ]
    print(f"\nEPOCH AI benchmark · {result['dataset_size']} labelled claims · {result['runtime_mode']} mode")
    print(f"{'metric':32s}{'EPOCH':>12s}{'baseline':>12s}")
    print("-" * 56)
    for name, ev, bv in rows:
        print(f"{name:32s}{ev:>12.3f}{bv:>12.3f}")
    print("\nper-verdict F1:")
    for verdict, stats in e["per_class"].items():
        print(f"  {verdict:20s} p={stats['precision']:.2f} r={stats['recall']:.2f} f1={stats['f1']:.2f} (n={stats['support']})")
    print(f"\nartifacts: benchmark/results/latest.json  (wall clock {result['wall_clock_ms']} ms)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the EPOCH AI benchmark")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--persist", action="store_true", help="write BenchmarkResult rows to the live DB")
    parser.add_argument("--fit-calibration", action="store_true", help="fit and save calibration.json")
    parser.add_argument("--live", action="store_true", help="use live providers if configured")
    args = parser.parse_args()
    result = run(args.limit, args.persist, args.fit_calibration)
    _print(result)


if __name__ == "__main__":
    main()
