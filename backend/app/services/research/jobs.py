"""Async job runner with observable states and a hard timeout."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from app.core.config import settings
from app.core.logging import log
from app.db.session import SessionLocal
from app.services.research.pipeline import ResearchPipeline


@dataclass
class JobHandle:
    research_id: str
    task: asyncio.Task | None = None
    state: str = "queued"
    errors: list[str] = field(default_factory=list)


_registry: dict[str, JobHandle] = {}


async def _execute(research_id: str) -> None:
    def work() -> None:
        db = SessionLocal()
        try:
            ResearchPipeline(db).run(research_id)
        finally:
            db.close()

    try:
        await asyncio.wait_for(asyncio.to_thread(work), timeout=settings.job_timeout_seconds)
        _registry[research_id].state = "succeeded"
    except asyncio.TimeoutError:
        _registry[research_id].state = "failed"
        _registry[research_id].errors.append("job timed out")
        _mark_failed(research_id, f"Job exceeded the {settings.job_timeout_seconds:.0f}s timeout.")
        log.error("job_timeout", extra={"event": "job_timeout", "research_id": research_id})
    except Exception as exc:  # noqa: BLE001 - already persisted by the pipeline
        _registry[research_id].state = "failed"
        _registry[research_id].errors.append(str(exc))
        log.error("job_failed", extra={"event": "job_failed", "research_id": research_id, "extra_data": str(exc)[:300]})


def _mark_failed(research_id: str, message: str) -> None:
    from app.db.models import ResearchSession

    db = SessionLocal()
    try:
        session = db.get(ResearchSession, research_id)
        if session and session.status not in {"succeeded", "failed"}:
            session.status = "failed"
            session.stage = "failed"
            session.error = message
            db.commit()
    finally:
        db.close()


def dispatch(research_id: str) -> JobHandle:
    """Fire-and-forget execution; the client polls the session resource."""
    handle = _registry.get(research_id)
    if handle and handle.task and not handle.task.done():
        return handle
    handle = JobHandle(research_id=research_id, state="running")
    _registry[research_id] = handle
    handle.task = asyncio.create_task(_execute(research_id))
    return handle


def job_state(research_id: str) -> str | None:
    handle = _registry.get(research_id)
    return handle.state if handle else None
