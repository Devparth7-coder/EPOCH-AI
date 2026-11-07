from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class PassageOut(BaseModel):
    id: str
    text: str
    relevance: float
    start_offset: int = 0

    model_config = {"from_attributes": True}


class SourceOut(BaseModel):
    id: str
    url: str
    canonical_url: str
    domain: str
    title: str
    publisher: str | None = None
    source_type: str
    published_at: datetime | None = None
    effective_at: datetime | None = None
    retrieved_at: datetime
    authority_score: float
    freshness_score: float
    is_superseded: bool = False
    version: str | None = None
    provider: str
    injection_flags: list[str] = Field(default_factory=list)
    passages: list[PassageOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class RelationshipOut(BaseModel):
    id: str
    claim_id: str
    source_id: str
    stance: str
    strength: float
    rationale: str
    conflict_kind: str | None = None

    model_config = {"from_attributes": True}


class TemporalObservationOut(BaseModel):
    id: str
    claim_id: str
    source_id: str | None = None
    observation_type: str
    detail: str
    published_at: datetime | None = None
    effective_at: datetime | None = None
    retrieved_at: datetime | None = None
    age_days: float | None = None
    decay_factor: float | None = None

    model_config = {"from_attributes": True}


class EvidenceBundle(BaseModel):
    research_id: str
    sources: list[SourceOut]
    relationships: list[RelationshipOut]
    temporal_observations: list[TemporalObservationOut]
    graph: dict


class ReportOut(BaseModel):
    research_id: str
    title: str
    original_query: str
    input_type: str
    depth: str
    runtime_mode: str
    overall_verdict: str
    confidence: float
    summary: str
    generated_at: datetime
    claims: list[dict]
    sources: list[SourceOut]
    temporal_observations: list[TemporalObservationOut]
    metrics: dict
    limitations: list[str] = Field(default_factory=list)
