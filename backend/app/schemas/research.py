from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.enums import Depth, InputType


class ResearchRequest(BaseModel):
    content: str = Field(..., min_length=3, max_length=20_000, description="Claim block, AI answer, or URL")
    input_type: InputType = InputType.TEXT
    depth: Depth = Depth.STANDARD
    title: str | None = Field(default=None, max_length=240)
    run_synchronously: bool = Field(
        default=False, description="Block until the pipeline finishes (used by tests / CLI)."
    )

    @field_validator("content")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3:
            raise ValueError("content must be at least 3 characters")
        return v


class StageState(BaseModel):
    stage: str
    label: str
    status: Literal["pending", "running", "done", "failed", "skipped"] = "pending"
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: float | None = None
    detail: str | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)


class ResearchCreateResponse(BaseModel):
    research_id: str
    status: str
    runtime_mode: str
    poll_url: str


class ClaimOut(BaseModel):
    id: str
    ordinal: int
    text: str
    claim_type: str
    entities: list[str] = Field(default_factory=list)
    numbers: list[str] = Field(default_factory=list)
    dates: list[str] = Field(default_factory=list)
    versions: list[str] = Field(default_factory=list)
    checkworthiness: float
    search_queries: list[str] = Field(default_factory=list)


class VerdictOut(BaseModel):
    claim_id: str
    verdict: str
    calibrated_probability: float
    evidence_quality: float
    supporting_count: int
    contradicting_count: int
    components: dict[str, float] = Field(default_factory=dict)
    explanation: str
    what_changed: str | None = None
    limitations: list[str] = Field(default_factory=list)


class ResearchSessionOut(BaseModel):
    id: str
    title: str
    original_query: str
    input_type: str
    depth: str
    status: str
    stage: str
    progress: float
    runtime_mode: str
    overall_verdict: str | None
    confidence: float | None
    summary: str | None
    error: str | None
    stage_states: list[StageState] = Field(default_factory=list)
    models_used: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    claim_count: int = 0
    evidence_count: int = 0

    model_config = {"from_attributes": True}
