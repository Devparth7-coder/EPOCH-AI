from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.config import settings
from app.core.security import sanitize_text
from app.schemas.research import ResearchRequest
from app.services.llm.gateway import gateway
from app.services.research.claim_extraction import extract_claims
from app.core.ratelimit import rate_limit

router = APIRouter(prefix="/claims", tags=["claims"], dependencies=[Depends(rate_limit)])


@router.post("/preview")
async def preview_claims(payload: ResearchRequest):
    """Extract claims without running a full investigation (fast, no persistence)."""
    text = sanitize_text(payload.content)
    gw = gateway()
    claims, meta = await extract_claims(text, gw, limit=settings.research_max_claims)
    return {
        "claims": claims,
        "meta": {
            **meta,
            "runtime_mode": settings.runtime_mode,
            "count": len(claims),
            "time_sensitive": sum(1 for c in claims if c["claim_type"] in {"version", "policy", "temporal"}),
        },
    }
