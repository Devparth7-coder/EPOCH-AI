from __future__ import annotations

import platform
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.ratelimit import rate_limit
from app.db.models import ModelExecutionLog, ResearchSession
from app.db.session import get_db

router = APIRouter(prefix="/system", tags=["system"])
ROUTER_START = time.time()


@router.get("/health")
def health(db: Session = Depends(get_db)):
    db_ok = True
    db_error = None
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        db_ok = False
        db_error = str(exc)[:200]

    providers = {
        "bifrost": {"configured": bool(settings.bifrost_api_key), "base_url": settings.bifrost_base_url or None},
        "openai": {"configured": bool(settings.openai_api_key)},
        "gemini": {"configured": bool(settings.gemini_api_key)},
        "tavily": {"configured": bool(settings.tavily_api_key)},
    }
    routing = [settings.model_primary] + (
        [settings.model_fallback] if settings.model_fallback != settings.model_primary else []
    )
    status = "healthy" if db_ok else "degraded"
    return {
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime_seconds": round(time.time() - ROUTER_START, 1),
        "version": "1.0.0",
        "environment": settings.environment,
        "runtime_mode": settings.runtime_mode,
        "mode_explanation": {
            "live": "Live model + live search providers configured.",
            "hybrid": "One provider family is live; the other runs on the deterministic engine.",
            "simulated": "No external credentials configured: deterministic engine + bundled evidence corpus. "
                         "All numbers shown are real measurements of this mode.",
        }[settings.runtime_mode],
        "database": {"ok": db_ok, "engine": settings.database_url.split("://")[0], "error": db_error},
        "providers": providers,
        "model_routing": {
            "primary": settings.model_primary,
            "fallback": settings.model_fallback,
            "chain": routing,
            "gateway": "bifrost" if settings.bifrost_api_key else ("openai" if settings.openai_api_key else ("gemini" if settings.gemini_api_key else "deterministic")),
        },
        "python": platform.python_version(),
        "limits": {
            "max_input_chars": settings.max_input_chars,
            "rate_limit_per_minute": settings.rate_limit_per_minute,
            "job_timeout_seconds": settings.job_timeout_seconds,
            "research_max_claims": settings.research_max_claims,
        },
    }


@router.get("/observability", dependencies=[Depends(rate_limit)])
def observability(db: Session = Depends(get_db)):
    logs = db.execute(
        select(
            ModelExecutionLog.provider,
            ModelExecutionLog.model,
            ModelExecutionLog.route,
            ModelExecutionLog.status,
            func.count(ModelExecutionLog.id),
            func.avg(ModelExecutionLog.latency_ms),
            func.sum(ModelExecutionLog.prompt_tokens),
            func.sum(ModelExecutionLog.completion_tokens),
            func.sum(ModelExecutionLog.cost_usd),
            func.sum(ModelExecutionLog.retries),
        ).group_by(
            ModelExecutionLog.provider,
            ModelExecutionLog.model,
            ModelExecutionLog.route,
            ModelExecutionLog.status,
        )
    ).all()

    by_model = [
        {
            "provider": provider,
            "model": model,
            "route": route,
            "status": status,
            "calls": int(calls),
            "mean_latency_ms": round(float(latency or 0), 2),
            "prompt_tokens": int(prompt or 0),
            "completion_tokens": int(completion or 0),
            "cost_usd": round(float(cost or 0), 6),
            "retries": int(retries or 0),
        }
        for provider, model, route, status, calls, latency, prompt, completion, cost, retries in logs
    ]

    sessions = db.execute(
        select(
            ResearchSession.status,
            func.count(ResearchSession.id),
            func.avg(ResearchSession.progress),
        ).group_by(ResearchSession.status)
    ).all()
    metrics_rows = db.execute(select(ResearchSession.metrics, ResearchSession.status)).all()
    searches = sum(int((m or {}).get("searches", 0)) for m, _ in metrics_rows)
    failed_searches = sum(int((m or {}).get("failed_searches", 0)) for m, _ in metrics_rows)
    latencies = [float((m or {}).get("pipeline_latency_ms", 0)) for m, s in metrics_rows if s == "succeeded"]
    stage_latency: dict[str, list[float]] = {}
    for row in db.execute(select(ResearchSession.stage_states)).all():
        for stage in row[0] or []:
            if stage.get("duration_ms") is not None:
                stage_latency.setdefault(stage["stage"], []).append(float(stage["duration_ms"]))

    total_tokens = sum(m["prompt_tokens"] + m["completion_tokens"] for m in by_model)
    total_cost = sum(m["cost_usd"] for m in by_model)
    failures = sum(m["calls"] for m in by_model if m["status"] not in {"ok"})
    verification_failures = sum(1 for _, s in metrics_rows if s == "failed")

    return {
        "runtime_mode": settings.runtime_mode,
        "gateway": "bifrost" if settings.bifrost_api_key else "direct",
        "model_routing": {
            "primary": settings.model_primary,
            "fallback": settings.model_fallback,
            "observed_routes": sorted({m["route"] for m in by_model}) or ["deterministic"],
        },
        "by_model": sorted(by_model, key=lambda m: -m["calls"]),
        "usage": {
            "total_calls": sum(m["calls"] for m in by_model),
            "total_tokens": total_tokens,
            "estimated_cost_usd": round(total_cost, 6),
            "provider_failures": failures,
        },
        "search": {"requests": searches, "failed_requests": failed_searches},
        "research": {
            "by_status": {status: int(count) for status, count, _ in sessions},
            "mean_execution_ms": round(sum(latencies) / len(latencies), 2) if latencies else 0.0,
            "verification_failures": verification_failures,
        },
        "stage_latency_ms": {
            stage: round(sum(values) / len(values), 2) for stage, values in stage_latency.items()
        },
        "notes": [
            "Every metric is aggregated from persisted execution logs; nothing is synthesised.",
            "In simulated mode model calls are deterministic and consume zero provider tokens.",
        ],
    }
