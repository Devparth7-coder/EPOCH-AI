"""SQLAlchemy 2.0 models — portable across SQLite (default) and PostgreSQL.

Everything a research session touches is persisted so a report can be replayed
byte-for-byte: original query, extracted claims, retrieved evidence, passages,
relationships, temporal observations, verdicts, execution logs and timestamps.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:20]}"


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


# --------------------------------------------------------------------------- #
# users
# --------------------------------------------------------------------------- #
class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("usr"))
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), default="Analyst")
    role: Mapped[str] = mapped_column(String(32), default="analyst")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    sessions: Mapped[list["ResearchSession"]] = relationship(back_populates="user")


# --------------------------------------------------------------------------- #
# research_sessions
# --------------------------------------------------------------------------- #
class ResearchSession(Base, TimestampMixin):
    __tablename__ = "research_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("rs"))
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)

    title: Mapped[str] = mapped_column(String(240), default="Untitled investigation")
    original_query: Mapped[str] = mapped_column(Text, nullable=False)
    input_type: Mapped[str] = mapped_column(String(24), default="text")  # text | url | ai_answer
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    depth: Mapped[str] = mapped_column(String(16), default="standard")  # quick | standard | deep

    # queued | running | succeeded | failed | cancelled
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)
    stage: Mapped[str] = mapped_column(String(32), default="queued")
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    overall_verdict: Mapped[str | None] = mapped_column(String(24), nullable=True, index=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    runtime_mode: Mapped[str] = mapped_column(String(16), default="simulated")
    models_used: Mapped[list] = mapped_column(JSON, default=list)
    stage_states: Mapped[list] = mapped_column(JSON, default=list)  # real execution states
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User | None] = relationship(back_populates="sessions")
    claims: Mapped[list["Claim"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="Claim.ordinal"
    )
    evidence: Mapped[list["EvidenceSource"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    verdicts: Mapped[list["Verdict"]] = relationship(back_populates="session", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_sessions_status_created", "status", "created_at"),)


# --------------------------------------------------------------------------- #
# claims
# --------------------------------------------------------------------------- #
class Claim(Base, TimestampMixin):
    __tablename__ = "claims"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("clm"))
    session_id: Mapped[str] = mapped_column(ForeignKey("research_sessions.id", ondelete="CASCADE"), index=True)
    ordinal: Mapped[int] = mapped_column(Integer, default=0)

    text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized: Mapped[str] = mapped_column(Text, default="")
    claim_type: Mapped[str] = mapped_column(String(32), default="factual")  # factual|numeric|temporal|version|policy
    entities: Mapped[list] = mapped_column(JSON, default=list)
    numbers: Mapped[list] = mapped_column(JSON, default=list)
    dates: Mapped[list] = mapped_column(JSON, default=list)
    versions: Mapped[list] = mapped_column(JSON, default=list)
    checkworthiness: Mapped[float] = mapped_column(Float, default=0.5)
    search_queries: Mapped[list] = mapped_column(JSON, default=list)
    parent_claim_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    extracted_by: Mapped[str] = mapped_column(String(64), default="heuristic")

    session: Mapped[ResearchSession] = relationship(back_populates="claims")
    verdict: Mapped["Verdict | None"] = relationship(back_populates="claim", uselist=False)


# --------------------------------------------------------------------------- #
# evidence_sources / evidence_passages
# --------------------------------------------------------------------------- #
class EvidenceSource(Base, TimestampMixin):
    __tablename__ = "evidence_sources"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("src"))
    session_id: Mapped[str] = mapped_column(ForeignKey("research_sessions.id", ondelete="CASCADE"), index=True)

    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    canonical_url: Mapped[str] = mapped_column(String(2048), default="")
    domain: Mapped[str] = mapped_column(String(255), default="")
    title: Mapped[str] = mapped_column(Text, default="")
    publisher: Mapped[str | None] = mapped_column(String(240), nullable=True)
    source_type: Mapped[str] = mapped_column(String(32), default="web")  # docs|news|blog|gov|wiki|paper|forum

    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    effective_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    authority_score: Mapped[float] = mapped_column(Float, default=0.5)
    freshness_score: Mapped[float] = mapped_column(Float, default=0.5)
    is_superseded: Mapped[bool] = mapped_column(Boolean, default=False)
    supersedes: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    version: Mapped[str | None] = mapped_column(String(64), nullable=True)

    content: Mapped[str] = mapped_column(Text, default="")
    raw_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    injection_flags: Mapped[list] = mapped_column(JSON, default=list)
    dedupe_key: Mapped[str] = mapped_column(String(64), default="")
    provider: Mapped[str] = mapped_column(String(32), default="tavily")

    session: Mapped[ResearchSession] = relationship(back_populates="evidence")
    passages: Mapped[list["EvidencePassage"]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )

    __table_args__ = (UniqueConstraint("session_id", "dedupe_key", name="uq_session_dedupe"),)


class EvidencePassage(Base, TimestampMixin):
    __tablename__ = "evidence_passages"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("psg"))
    source_id: Mapped[str] = mapped_column(ForeignKey("evidence_sources.id", ondelete="CASCADE"), index=True)
    claim_id: Mapped[str | None] = mapped_column(ForeignKey("claims.id", ondelete="SET NULL"), nullable=True, index=True)

    text: Mapped[str] = mapped_column(Text, default="")
    start_offset: Mapped[int] = mapped_column(Integer, default=0)
    relevance: Mapped[float] = mapped_column(Float, default=0.0)
    embedding: Mapped[list] = mapped_column(JSON, default=list)  # portable; pgvector optional

    source: Mapped[EvidenceSource] = relationship(back_populates="passages")


class ClaimEvidenceRelationship(Base, TimestampMixin):
    __tablename__ = "claim_evidence_relationships"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("rel"))
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("evidence_sources.id", ondelete="CASCADE"), index=True)
    passage_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # supports | contradicts | context_only | supersedes
    stance: Mapped[str] = mapped_column(String(24), default="context_only")
    strength: Mapped[float] = mapped_column(Float, default=0.0)
    rationale: Mapped[str] = mapped_column(Text, default="")
    conflict_kind: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False)


class TemporalObservation(Base, TimestampMixin):
    __tablename__ = "temporal_observations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("tmp"))
    session_id: Mapped[str] = mapped_column(ForeignKey("research_sessions.id", ondelete="CASCADE"), index=True)
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    observation_type: Mapped[str] = mapped_column(String(40), default="recency")  # recency|superseded|expired|version_drift|future_effective
    detail: Mapped[str] = mapped_column(Text, default="")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    effective_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    age_days: Mapped[float | None] = mapped_column(Float, nullable=True)
    decay_factor: Mapped[float | None] = mapped_column(Float, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class Verdict(Base, TimestampMixin):
    __tablename__ = "verdicts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("vrd"))
    session_id: Mapped[str] = mapped_column(ForeignKey("research_sessions.id", ondelete="CASCADE"), index=True)
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), unique=True, index=True)

    verdict: Mapped[str] = mapped_column(String(24), default="UNVERIFIED")
    calibrated_probability: Mapped[float] = mapped_column(Float, default=0.5)
    evidence_quality: Mapped[float] = mapped_column(Float, default=0.0)
    supporting_count: Mapped[int] = mapped_column(Integer, default=0)
    contradicting_count: Mapped[int] = mapped_column(Integer, default=0)
    components: Mapped[dict] = mapped_column(JSON, default=dict)  # authority/relevance/temporal/corroboration/contradiction
    explanation: Mapped[str] = mapped_column(Text, default="")
    what_changed: Mapped[str | None] = mapped_column(Text, nullable=True)
    limitations: Mapped[list] = mapped_column(JSON, default=list)
    decided_by: Mapped[str] = mapped_column(String(64), default="verdict-engine/v1")

    session: Mapped[ResearchSession] = relationship(back_populates="verdicts")
    claim: Mapped[Claim] = relationship(back_populates="verdict")


class ModelExecutionLog(Base, TimestampMixin):
    __tablename__ = "model_execution_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("log"))
    session_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String(32), default="bifrost")
    model: Mapped[str] = mapped_column(String(120), default="")
    task: Mapped[str] = mapped_column(String(64), default="")
    route: Mapped[str] = mapped_column(String(16), default="primary")  # primary | fallback | deterministic
    status: Mapped[str] = mapped_column(String(16), default="ok")
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    retries: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class BenchmarkResult(Base, TimestampMixin):
    __tablename__ = "benchmark_results"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("bmk"))
    run_label: Mapped[str] = mapped_column(String(120), default="")
    system: Mapped[str] = mapped_column(String(40), default="epoch")  # epoch | llm_baseline
    dataset_version: Mapped[str] = mapped_column(String(32), default="v1")
    claim_count: Mapped[int] = mapped_column(Integer, default=0)
    runtime_mode: Mapped[str] = mapped_column(String(16), default="simulated")
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    confusion: Mapped[dict] = mapped_column(JSON, default=dict)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    notes: Mapped[Text] = mapped_column(Text, default="")
