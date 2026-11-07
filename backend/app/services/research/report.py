"""Report + evidence-graph assembly (pure functions over persisted rows)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Claim,
    ClaimEvidenceRelationship,
    EvidenceSource,
    ResearchSession,
    TemporalObservation,
    Verdict,
)


def load_session(db: Session, research_id: str) -> ResearchSession | None:
    return db.get(ResearchSession, research_id)


def claims_with_verdicts(db: Session, research_id: str) -> list[dict]:
    claims = db.scalars(select(Claim).where(Claim.session_id == research_id).order_by(Claim.ordinal)).all()
    verdicts = {v.claim_id: v for v in db.scalars(select(Verdict).where(Verdict.session_id == research_id))}
    relationships = db.scalars(
        select(ClaimEvidenceRelationship).where(
            ClaimEvidenceRelationship.claim_id.in_([c.id for c in claims] or [""])
        )
    ).all()
    sources = {s.id: s for s in db.scalars(select(EvidenceSource).where(EvidenceSource.session_id == research_id))}
    out: list[dict] = []
    for claim in claims:
        verdict = verdicts.get(claim.id)
        rels = [r for r in relationships if r.claim_id == claim.id]
        out.append(
            {
                "id": claim.id,
                "ordinal": claim.ordinal,
                "text": claim.text,
                "claim_type": claim.claim_type,
                "entities": claim.entities or [],
                "numbers": claim.numbers or [],
                "dates": claim.dates or [],
                "versions": claim.versions or [],
                "checkworthiness": claim.checkworthiness,
                "search_queries": claim.search_queries or [],
                "verdict": {
                    "verdict": verdict.verdict,
                    "calibrated_probability": verdict.calibrated_probability,
                    "evidence_quality": verdict.evidence_quality,
                    "supporting_count": verdict.supporting_count,
                    "contradicting_count": verdict.contradicting_count,
                    "components": verdict.components or {},
                    "explanation": verdict.explanation,
                    "what_changed": verdict.what_changed,
                    "limitations": verdict.limitations or [],
                }
                if verdict
                else None,
                "evidence": [
                    {
                        "source_id": r.source_id,
                        "url": sources[r.source_id].url if r.source_id in sources else "",
                        "title": sources[r.source_id].title if r.source_id in sources else "",
                        "domain": sources[r.source_id].domain if r.source_id in sources else "",
                        "publisher": sources[r.source_id].publisher if r.source_id in sources else None,
                        "published_at": _iso(sources[r.source_id].published_at) if r.source_id in sources else None,
                        "retrieved_at": _iso(sources[r.source_id].retrieved_at) if r.source_id in sources else None,
                        "authority_score": sources[r.source_id].authority_score if r.source_id in sources else 0,
                        "stance": r.stance,
                        "strength": r.strength,
                        "rationale": r.rationale,
                        "conflict_kind": r.conflict_kind,
                    }
                    for r in rels
                ],
            }
        )
    return out


def build_graph(db: Session, research_id: str) -> dict:
    """Claim nodes + source nodes + stance edges + temporal nodes."""
    claims = claims_with_verdicts(db, research_id)
    sources = db.scalars(select(EvidenceSource).where(EvidenceSource.session_id == research_id)).all()
    observations = db.scalars(
        select(TemporalObservation).where(TemporalObservation.session_id == research_id)
    ).all()
    rels = db.scalars(
        select(ClaimEvidenceRelationship).where(
            ClaimEvidenceRelationship.claim_id.in_([c["id"] for c in claims] or [""])
        )
    ).all()

    nodes: list[dict] = []
    for claim in claims:
        nodes.append(
            {
                "id": claim["id"],
                "kind": "claim",
                "label": claim["text"],
                "verdict": (claim["verdict"] or {}).get("verdict"),
                "evidence_quality": (claim["verdict"] or {}).get("evidence_quality", 0),
                "claim_type": claim["claim_type"],
            }
        )
    for source in sources:
        nodes.append(
            {
                "id": source.id,
                "kind": "source",
                "label": source.title,
                "domain": source.domain,
                "source_type": source.source_type,
                "url": source.url,
                "authority": source.authority_score,
                "freshness": source.freshness_score,
                "published_at": _iso(source.published_at),
                "effective_at": _iso(source.effective_at),
                "retrieved_at": _iso(source.retrieved_at),
                "version": source.version,
                "is_superseded": source.is_superseded,
            }
        )
    for obs in observations:
        if obs.observation_type in {"version_drift", "expired", "superseded", "future_effective"}:
            nodes.append(
                {
                    "id": obs.id,
                    "kind": "temporal",
                    "label": obs.observation_type.replace("_", " ").title(),
                    "detail": obs.detail,
                    "claim_id": obs.claim_id,
                    "source_id": obs.source_id,
                    "observation_type": obs.observation_type,
                    "published_at": _iso(obs.published_at),
                }
            )

    links: list[dict] = [
        {
            "id": r.id,
            "source": r.claim_id,
            "target": r.source_id,
            "stance": r.stance,
            "strength": r.strength,
            "rationale": r.rationale,
        }
        for r in rels
    ]
    for obs in observations:
        if obs.observation_type in {"version_drift", "expired", "superseded", "future_effective"}:
            links.append(
                {
                    "id": f"{obs.id}_link",
                    "source": obs.claim_id,
                    "target": obs.id,
                    "stance": "temporal",
                    "strength": obs.decay_factor or 0.5,
                    "rationale": obs.detail,
                }
            )
    return {
        "nodes": nodes,
        "links": links,
        "counts": {
            "claims": len(claims),
            "sources": len(sources),
            "supports": sum(1 for link in links if link["stance"] == "supports"),
            "contradicts": sum(1 for link in links if link["stance"] == "contradicts"),
            "temporal": sum(1 for link in links if link["stance"] == "temporal"),
        },
    }


def build_report(db: Session, session: ResearchSession) -> dict | None:
    claims = claims_with_verdicts(db, session.id)
    if not claims:
        return None
    sources = db.scalars(
        select(EvidenceSource).where(EvidenceSource.session_id == session.id)
    ).all()
    observations = db.scalars(
        select(TemporalObservation).where(TemporalObservation.session_id == session.id)
    ).all()
    limitations: list[str] = []
    for claim in claims:
        if claim["verdict"]:
            limitations.extend(claim["verdict"].get("limitations") or [])
    if not observations:
        limitations.append("No dated evidence was retrieved, so temporal validity rests on retrieval time only.")
    return {
        "research_id": session.id,
        "title": session.title,
        "original_query": session.original_query,
        "input_type": session.input_type,
        "depth": session.depth,
        "runtime_mode": session.runtime_mode,
        "overall_verdict": session.overall_verdict or "UNVERIFIED",
        "confidence": session.confidence or 0.0,
        "summary": session.summary or "",
        "generated_at": _iso(session.completed_at or datetime.now(timezone.utc)),
        "claims": claims,
        "sources": [_source_dict(s) for s in sources],
        "temporal_observations": [
            {
                "id": o.id,
                "claim_id": o.claim_id,
                "source_id": o.source_id,
                "observation_type": o.observation_type,
                "detail": o.detail,
                "published_at": _iso(o.published_at),
                "effective_at": _iso(o.effective_at),
                "retrieved_at": _iso(o.retrieved_at),
                "age_days": o.age_days,
                "decay_factor": o.decay_factor,
            }
            for o in observations
        ],
        "metrics": session.metrics or {},
        "limitations": list(dict.fromkeys(limitations))[:8],
        "calibration": _calibration_note(),
    }


def _calibration_note() -> dict:
    from app.services.research.scoring import load_calibration

    cal = load_calibration()
    return {
        "method": "platt-style logistic mapping",
        "trained_on": cal.get("trained_on", "default-prior"),
        "n": cal.get("n", 0),
        "note": (
            "Calibrated probabilities come from the labelled benchmark when available; otherwise documented "
            "priors are used and labelled as such."
        ),
    }


def _source_dict(source: EvidenceSource) -> dict:
    return {
        "id": source.id,
        "url": source.url,
        "canonical_url": source.canonical_url,
        "domain": source.domain,
        "title": source.title,
        "publisher": source.publisher,
        "source_type": source.source_type,
        "published_at": _iso(source.published_at),
        "effective_at": _iso(source.effective_at),
        "retrieved_at": _iso(source.retrieved_at),
        "authority_score": source.authority_score,
        "freshness_score": source.freshness_score,
        "is_superseded": source.is_superseded,
        "version": source.version,
        "provider": source.provider,
        "injection_flags": source.injection_flags or [],
        "passages": [
            {"id": p.id, "text": p.text, "relevance": p.relevance, "start_offset": p.start_offset}
            for p in (source.passages or [])
        ],
    }


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()
