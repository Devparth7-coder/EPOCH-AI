from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.ratelimit import rate_limit
from app.db.models import Claim, ResearchSession
from app.db.session import get_db

router = APIRouter(prefix="/history", tags=["history"], dependencies=[Depends(rate_limit)])


@router.get("")
def list_history(
    db: Session = Depends(get_db),
    q: str | None = Query(default=None, max_length=200),
    verdict: str | None = Query(default=None, max_length=40),
    status: str | None = Query(default=None, max_length=20),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    stmt = select(ResearchSession)
    count_stmt = select(func.count(ResearchSession.id))

    filters = []
    if q:
        like = f"%{q.lower()}%"
        filters.append(or_(func.lower(ResearchSession.title).like(like), func.lower(ResearchSession.original_query).like(like)))
    if verdict:
        filters.append(ResearchSession.overall_verdict == verdict)
    if status:
        filters.append(ResearchSession.status == status)
    if date_from:
        filters.append(ResearchSession.created_at >= date_from)
    if date_to:
        filters.append(ResearchSession.created_at <= date_to)
    for f in filters:
        stmt = stmt.where(f)
        count_stmt = count_stmt.where(f)

    total = db.scalar(count_stmt) or 0
    rows = db.scalars(
        stmt.order_by(ResearchSession.created_at.desc()).limit(limit).offset(offset)
    ).all()
    claim_counts = dict(
        db.execute(
            select(Claim.session_id, func.count(Claim.id))
            .where(Claim.session_id.in_([r.id for r in rows] or [""]))
            .group_by(Claim.session_id)
        ).all()
    )
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [
            {
                "id": r.id,
                "title": r.title,
                "excerpt": r.original_query[:240],
                "input_type": r.input_type,
                "depth": r.depth,
                "status": r.status,
                "stage": r.stage,
                "overall_verdict": r.overall_verdict,
                "confidence": r.confidence,
                "runtime_mode": r.runtime_mode,
                "claim_count": claim_counts.get(r.id, 0),
                "created_at": r.created_at,
                "completed_at": r.completed_at,
            }
            for r in rows
        ],
    }
