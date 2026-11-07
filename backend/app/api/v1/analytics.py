from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.ratelimit import rate_limit
from app.db.models import BenchmarkResult, Claim, EvidenceSource, ModelExecutionLog, ResearchSession, Verdict
from app.db.session import get_db

router = APIRouter(prefix="/analytics", tags=["analytics"], dependencies=[Depends(rate_limit)])

OUTDATED = {"OUTDATED", "PARTIALLY_OUTDATED"}


@router.get("")
def analytics(db: Session = Depends(get_db), days: int = 14):
    total_sessions = db.scalar(select(func.count(ResearchSession.id))) or 0
    completed = db.scalar(
        select(func.count(ResearchSession.id)).where(ResearchSession.status == "succeeded")
    ) or 0
    failed = db.scalar(select(func.count(ResearchSession.id)).where(ResearchSession.status == "failed")) or 0
    total_claims = db.scalar(select(func.count(Claim.id))) or 0
    total_sources = db.scalar(select(func.count(EvidenceSource.id))) or 0

    verdict_rows = db.execute(select(Verdict.verdict, func.count(Verdict.id)).group_by(Verdict.verdict)).all()
    distribution = {verdict: count for verdict, count in verdict_rows}
    verdict_total = sum(distribution.values())
    outdated_detected = sum(count for v, count in distribution.items() if v in OUTDATED)
    mean_quality = db.scalar(select(func.avg(Verdict.evidence_quality))) or 0.0
    mean_prob = db.scalar(select(func.avg(Verdict.calibrated_probability))) or 0.0

    claim_type_rows = db.execute(select(Claim.claim_type, func.count(Claim.id)).group_by(Claim.claim_type)).all()

    recent = db.scalars(select(ResearchSession).order_by(ResearchSession.created_at.desc()).limit(8)).all()
    recent_ids = [r.id for r in recent]
    recent_claims = dict(
        db.execute(
            select(Claim.session_id, func.count(Claim.id))
            .where(Claim.session_id.in_(recent_ids or [""]))
            .group_by(Claim.session_id)
        ).all()
    )

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    activity: list[dict] = []
    rows = db.execute(
        select(ResearchSession.created_at, ResearchSession.status, ResearchSession.metrics)
        .where(ResearchSession.created_at >= cutoff)
    ).all()
    buckets: dict[str, dict] = {}
    for i in range(days):
        day = (cutoff + timedelta(days=i + 1)).date().isoformat()
        buckets[day] = {"date": day, "investigations": 0, "evidence": 0}
    for created_at, status, metrics in rows:
        key = created_at.date().isoformat()
        if key in buckets:
            buckets[key]["investigations"] += 1
            buckets[key]["evidence"] += int((metrics or {}).get("evidence_count", 0))
    activity = list(buckets.values())

    domain_rows = db.execute(
        select(EvidenceSource.domain, func.count(EvidenceSource.id), func.avg(EvidenceSource.authority_score))
        .group_by(EvidenceSource.domain)
        .order_by(func.count(EvidenceSource.id).desc())
        .limit(10)
    ).all()

    latencies = [float((m or {}).get("pipeline_latency_ms", 0)) for (m,) in db.execute(
        select(ResearchSession.metrics).where(ResearchSession.status == "succeeded")
    ).all()]
    tokens = db.scalar(select(func.sum(ModelExecutionLog.prompt_tokens + ModelExecutionLog.completion_tokens))) or 0
    cost = db.scalar(select(func.sum(ModelExecutionLog.cost_usd))) or 0.0
    benchmark = db.scalars(select(BenchmarkResult).order_by(BenchmarkResult.created_at.desc()).limit(4)).all()

    return {
        "runtime_mode": settings.runtime_mode,
        "totals": {
            "sessions": total_sessions,
            "completed": completed,
            "failed": failed,
            "claims_analyzed": total_claims,
            "sources_retrieved": total_sources,
            "outdated_detected": outdated_detected,
            "verdicts_issued": verdict_total,
        },
        "verdict_distribution": distribution,
        "claim_type_distribution": {k: v for k, v in claim_type_rows},
        "quality": {
            "mean_evidence_quality": round(float(mean_quality), 4),
            "mean_calibrated_probability": round(float(mean_prob), 4),
        },
        "performance": {
            "mean_pipeline_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else 0.0,
            "max_pipeline_latency_ms": round(max(latencies), 2) if latencies else 0.0,
            "tokens_consumed": int(tokens),
            "estimated_cost_usd": round(float(cost), 6),
        },
        "activity": activity,
        "top_domains": [
            {"domain": d, "count": c, "mean_authority": round(float(a or 0), 3)} for d, c, a in domain_rows
        ],
        "recent": [
            {
                "id": r.id,
                "title": r.title,
                "status": r.status,
                "overall_verdict": r.overall_verdict,
                "confidence": r.confidence,
                "claim_count": recent_claims.get(r.id, 0),
                "created_at": r.created_at,
                "runtime_mode": r.runtime_mode,
            }
            for r in recent
        ],
        "benchmarks": [
            {
                "id": b.id,
                "run_label": b.run_label,
                "system": b.system,
                "claim_count": b.claim_count,
                "runtime_mode": b.runtime_mode,
                "metrics": b.metrics,
                "created_at": b.created_at,
            }
            for b in benchmark
        ],
    }
