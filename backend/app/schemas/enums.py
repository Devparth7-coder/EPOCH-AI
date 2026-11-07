from __future__ import annotations

from enum import StrEnum


class Verdict(StrEnum):
    VERIFIED = "VERIFIED"
    PARTIALLY_OUTDATED = "PARTIALLY_OUTDATED"
    OUTDATED = "OUTDATED"
    CONTRADICTED = "CONTRADICTED"
    UNVERIFIED = "UNVERIFIED"
    CONFLICTING = "CONFLICTING"


class Stance(StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    CONTEXT_ONLY = "context_only"
    SUPERSEDES = "supersedes"


class Depth(StrEnum):
    QUICK = "quick"
    STANDARD = "standard"
    DEEP = "deep"


class InputType(StrEnum):
    TEXT = "text"
    URL = "url"
    AI_ANSWER = "ai_answer"


class Stage(StrEnum):
    QUEUED = "queued"
    EXTRACTING_CLAIMS = "extracting_claims"
    PLANNING_RESEARCH = "planning_research"
    RETRIEVING_EVIDENCE = "retrieving_evidence"
    ANALYZING_TEMPORAL = "analyzing_temporal"
    DETECTING_CONTRADICTIONS = "detecting_contradictions"
    GENERATING_VERDICTS = "generating_verdicts"
    COMPLETE = "complete"
    FAILED = "failed"


STAGE_ORDER: list[str] = [
    Stage.EXTRACTING_CLAIMS,
    Stage.PLANNING_RESEARCH,
    Stage.RETRIEVING_EVIDENCE,
    Stage.ANALYZING_TEMPORAL,
    Stage.DETECTING_CONTRADICTIONS,
    Stage.GENERATING_VERDICTS,
]

STAGE_LABELS: dict[str, str] = {
    Stage.EXTRACTING_CLAIMS: "Extracting claims",
    Stage.PLANNING_RESEARCH: "Planning research",
    Stage.RETRIEVING_EVIDENCE: "Retrieving evidence",
    Stage.ANALYZING_TEMPORAL: "Analyzing temporal validity",
    Stage.DETECTING_CONTRADICTIONS: "Detecting contradictions",
    Stage.GENERATING_VERDICTS: "Generating verdicts",
}
