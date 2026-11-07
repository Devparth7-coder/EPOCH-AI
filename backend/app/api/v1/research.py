from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import NotFoundError, UnsafeURLError
from app.core.logging import log
from app.core.ratelimit import rate_limit
from app.core.security import sanitize_text
from app.db.models import Claim, EvidenceSource, ResearchSession
from app.db.session import get_db
from app.db.seed import ensure_default_user
from app.schemas.research import ResearchCreateResponse, ResearchRequest
from app.services.research import retrieval
from app.services.research.jobs import dispatch
from app.services.research.pipeline import ResearchPipeline
from app.services.research.report import build_graph, build_report, claims_with_verdicts

router = APIRouter(prefix="/research", tags=["research"], dependencies=[Depends(rate_limit)])


def _title_from(text: str, explicit: str | None) -> str:
    if explicit:
        return explicit[:240]
    first = text.strip().split("\n")[0]
    return (first[:117] + "…") if len(first) > 120 else (first or "Untitled investigation")


@router.post("", response_model=ResearchCreateResponse, status_code=201)
async def create_research(payload: ResearchRequest, db: Session = Depends(get_db)):
    user = ensure_default_user(db)
    body = payload.content

    if payload.input_type == "url":
        try:
            title, extracted = await retrieval.fetch_url_document(body)
        except UnsafeURLError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=f"Could not fetch URL: {exc}") from exc
        if len(extracted) < 60:
            raise HTTPException(status_code=400, detail="Fetched page contains too little text to analyse.")
        body = sanitize_text(extracted)
        source_url = payload.content.strip()
        title_hint = payload.title or title
    else:
        body = sanitize_text(body)
        source_url = None
        title_hint = payload.title

    session = ResearchSession(
        user_id=user.id,
        title=_title_from(title_hint or body, payload.title),
        original_query=body,
        input_type=str(payload.input_type),
        source_url=source_url,
        depth=str(payload.depth),
        status="queued",
        stage="queued",
        progress=0.0,
        runtime_mode=settings.runtime_mode,
        stage_states=[],
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    log.info("research_created", extra={"event": "research_created", "research_id": session.id})

    if payload.run_synchronously:
        ResearchPipeline(db).run(session.id)
        db.refresh(session)
    else:
        dispatch(session.id)

    return ResearchCreateResponse(
        research_id=session.id,
        status=session.status,
        runtime_mode=session.runtime_mode,
        poll_url=f"{settings.api_v1_prefix}/research/{session.id}",
    )


@router.get("/{research_id}")
def get_research(research_id: str, db: Session = Depends(get_db)):
    session = db.get(ResearchSession, research_id)
    if session is None:
        raise NotFoundError(f"Research session {research_id} not found.")
    claim_count = db.scalar(select(func.count(Claim.id)).where(Claim.session_id == research_id)) or 0
    evidence_count = db.scalar(
        select(func.count(EvidenceSource.id)).where(EvidenceSource.session_id == research_id)
    ) or 0
    claims = claims_with_verdicts(db, research_id) if session.status == "succeeded" else []
    return {
        "id": session.id,
        "title": session.title,
        "original_query": session.original_query,
        "input_type": session.input_type,
        "source_url": session.source_url,
        "depth": session.depth,
        "status": session.status,
        "stage": session.stage,
        "progress": session.progress,
        "runtime_mode": session.runtime_mode,
        "overall_verdict": session.overall_verdict,
        "confidence": session.confidence,
        "summary": session.summary,
        "error": session.error,
        "stage_states": session.stage_states or [],
        "models_used": session.models_used or [],
        "metrics": session.metrics or {},
        "created_at": session.created_at,
        "started_at": session.started_at,
        "completed_at": session.completed_at,
        "claim_count": claim_count,
        "evidence_count": evidence_count,
        "claims": claims,
    }


@router.get("/{research_id}/evidence")
def get_evidence(research_id: str, db: Session = Depends(get_db)):
    session = db.get(ResearchSession, research_id)
    if session is None:
        raise NotFoundError(f"Research session {research_id} not found.")
    graph = build_graph(db, research_id)
    report = build_report(db, session)
    return {
        "research_id": research_id,
        "sources": (report or {}).get("sources", []),
        "temporal_observations": (report or {}).get("temporal_observations", []),
        "claims": [
            {
                "id": c["id"],
                "text": c["text"],
                "claim_type": c["claim_type"],
                "verdict": (c["verdict"] or {}).get("verdict"),
                "evidence": c["evidence"],
            }
            for c in ((report or {}).get("claims") or [])
        ],
        "graph": graph,
    }


@router.get("/{research_id}/report")
def get_report(research_id: str, db: Session = Depends(get_db)):
    session = db.get(ResearchSession, research_id)
    if session is None:
        raise NotFoundError(f"Research session {research_id} not found.")
    report = build_report(db, session)
    if report is None:
        raise NotFoundError("Report is not available yet; this investigation has no persisted claims.")
    return report
