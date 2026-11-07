"""End-to-end research pipeline.

Order of execution is fixed and observable:
    1 extract claims → 2 plan research → 3 retrieve evidence →
    4 temporal analysis → 5 contradiction detection → 6 verdicts

Every stage writes its own timing/metrics to `research_sessions.stage_states`
before the next one starts, so the client renders real execution states and
never a fabricated progress bar.
"""
from __future__ import annotations

import time
import traceback
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import settings
from app.core.logging import log
from app.db.models import (
    Claim,
    ClaimEvidenceRelationship,
    EvidencePassage,
    EvidenceSource,
    ModelExecutionLog,
    ResearchSession,
    TemporalObservation,
    Verdict,
)
from app.schemas.enums import STAGE_LABELS, STAGE_ORDER, Stage, Verdict as VerdictEnum
from app.services.llm.gateway import LLMGateway, gateway
from app.services.research import claim_extraction, contradiction, planner, retrieval, temporal, textutil as tu
from app.services.research.verdict import decide, overall


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _stage_template() -> list[dict]:
    return [
        {"stage": s, "label": STAGE_LABELS[s], "status": "pending", "started_at": None,
         "finished_at": None, "duration_ms": None, "detail": None, "metrics": {}}
        for s in STAGE_ORDER
    ]


def _mark(states: list[dict], stage: str, status: str, **kwargs) -> None:
    for state in states:
        if state["stage"] == stage:
            state["status"] = status
            if status == "running":
                state["started_at"] = _now().isoformat()
            if status in {"done", "failed", "skipped"}:
                state["finished_at"] = _now().isoformat()
                if state.get("started_at"):
                    started = datetime.fromisoformat(state["started_at"])
                    state["duration_ms"] = round((_now() - started).total_seconds() * 1000, 2)
            for key, value in kwargs.items():
                state[key] = value
            break


def _progress(states: list[dict]) -> float:
    done = sum(1 for s in states if s["status"] in {"done", "skipped"})
    return round(done / max(1, len(states)), 3)


class ResearchPipeline:
    def __init__(
        self,
        db: Session,
        gw: LLMGateway | None = None,
        fixtures: dict[str, list[dict]] | None = None,
    ) -> None:
        self.db = db
        self.gw = gw or gateway()
        # Deterministic evidence fixtures (benchmark mode). None → live/corpus retrieval.
        self.fixtures = fixtures

    # ------------------------------------------------------------------ #
    def run(self, session_id: str) -> ResearchSession:
        session = self.db.get(ResearchSession, session_id)
        if session is None:
            raise ValueError(f"research session {session_id} not found")

        started_perf = time.perf_counter()
        session.status = "running"
        session.started_at = _now()
        session.stage = Stage.EXTRACTING_CLAIMS
        session.stage_states = _stage_template()
        session.runtime_mode = settings.runtime_mode
        self.db.commit()

        tokens = 0
        cost = 0.0
        try:
            # ---------------- 1. claim extraction -------------------------
            _mark(session.stage_states, Stage.EXTRACTING_CLAIMS, "running", detail="Parsing input into atomic claims")
            self._sync(session)
            limit = {"quick": 5, "standard": settings.research_max_claims, "deep": settings.research_max_claims}.get(
                session.depth, settings.research_max_claims
            )
            raw_claims, meta = self._await(
                claim_extraction.extract_claims(session.original_query, self.gw, limit)
            )
            claims = [self._persist_claim(session, c) for c in raw_claims]
            tokens += int(meta.get("tokens", 0) or 0)
            cost += float(meta.get("cost_usd", 0.0) or 0.0)
            _mark(
                session.stage_states, Stage.EXTRACTING_CLAIMS, "done",
                detail=f"{len(claims)} atomic claims extracted ({meta.get('method')} engine)",
                metrics={"claims": len(claims), "method": meta.get("method"), "model": meta.get("model")},
            )
            session.stage = Stage.PLANNING_RESEARCH
            self._sync(session)

            if not claims:
                raise ValueError("No checkworthy claims could be extracted from the input.")

            # ---------------- 2. research planning ------------------------
            _mark(session.stage_states, Stage.PLANNING_RESEARCH, "running", detail="Building targeted search plan")
            self._sync(session)
            plans, plan_meta = self._await(
                planner.plan_research([c["payload"] for c in claims], session.depth, self.gw)
            )
            for claim, plan in zip(claims, plans):
                claim["row"].search_queries = plan["queries"]
                claim["payload"]["search_queries"] = plan["queries"]
            tokens += int(plan_meta.get("tokens", 0) or 0)
            cost += float(plan_meta.get("cost_usd", 0.0) or 0.0)
            total_queries = sum(len(p["queries"]) for p in plans)
            _mark(
                session.stage_states, Stage.PLANNING_RESEARCH, "done",
                detail=f"{total_queries} targeted queries across {len(plans)} claims",
                metrics={"queries": total_queries, "method": plan_meta.get("method")},
            )
            session.stage = Stage.RETRIEVING_EVIDENCE
            self._sync(session)

            # ---------------- 3. evidence retrieval -----------------------
            _mark(session.stage_states, Stage.RETRIEVING_EVIDENCE, "running", detail="Searching live sources")
            self._sync(session)
            sources, retrieval_meta = self._await(
                retrieval.retrieve_evidence(
                    [c["payload"] for c in claims], plans, depth=session.depth, fixtures=self.fixtures
                )
            )
            persisted_sources = self._persist_sources(session, sources)
            sources_by_url = {s["url"]: s for s in sources}
            _mark(
                session.stage_states, Stage.RETRIEVING_EVIDENCE, "done",
                detail=(
                    f"{retrieval_meta['unique_sources']} unique sources from "
                    f"{retrieval_meta['searches']} searches ({retrieval_meta['provider']})"
                ),
                metrics=retrieval_meta,
            )
            cost += float(retrieval_meta.get("search_cost_usd", 0.0) or 0.0)
            session.stage = Stage.ANALYZING_TEMPORAL
            self._sync(session)

            if not sources:
                observations, source_updates, signals = [], {}, {}
                relationships: list[dict] = []
            else:
                # preliminary associations let the temporal engine reason per claim
                preliminary = contradiction.build_relationships_heuristic(
                    [c["payload"] for c in claims], sources
                )

                # ---------------- 4. temporal analysis --------------------
                _mark(session.stage_states, Stage.ANALYZING_TEMPORAL, "running",
                      detail="Resolving publication vs effective dates")
                self._sync(session)
                observations, source_updates, signals = temporal.analyze_temporal(
                    [c["payload"] for c in claims], sources, preliminary
                )
                self._apply_source_updates(persisted_sources, source_updates)
                self._persist_observations(session, claims, persisted_sources, observations)
                drift = sum(1 for s in signals.values() if s.get("version_drift"))
                expired = sum(1 for s in signals.values() if s.get("expired"))
                _mark(
                    session.stage_states, Stage.ANALYZING_TEMPORAL, "done",
                    detail=(
                        f"{len(observations)} temporal observations · {drift} version drift · "
                        f"{expired} time-anchored claims overtaken"
                    ),
                    metrics={"observations": len(observations), "version_drift": drift, "expired": expired},
                )
                session.stage = Stage.DETECTING_CONTRADICTIONS
                self._sync(session)

                # ---------------- 5. contradiction detection --------------
                _mark(session.stage_states, Stage.DETECTING_CONTRADICTIONS, "running",
                      detail="Classifying stance of every evidence pair")
                self._sync(session)
                relationships, contra_meta = self._await(
                    contradiction.detect_relationships([c["payload"] for c in claims], sources, self.gw)
                )
                cost += float(contra_meta.get("cost_usd", 0.0) or 0.0)
                self._persist_relationships(session, claims, persisted_sources, relationships)
                supports = sum(1 for r in relationships if r["stance"] == "supports")
                contradicts = sum(1 for r in relationships if r["stance"] == "contradicts")
                _mark(
                    session.stage_states, Stage.DETECTING_CONTRADICTIONS, "done",
                    detail=f"{supports} supporting · {contradicts} contradicting relationships",
                    metrics={"pairs": len(relationships), "supports": supports, "contradicts": contradicts},
                )

            session.stage = Stage.GENERATING_VERDICTS
            self._sync(session)

            # ---------------- 6. verdicts --------------------------------
            _mark(session.stage_states, Stage.GENERATING_VERDICTS, "running",
                  detail="Applying verdict rules and calibration")
            self._sync(session)
            verdict_rows = []
            for claim in claims:
                claim_rels = [r for r in relationships if r["claim_key"] == claim["payload"]["text"]]
                signal = signals.get(claim["payload"]["text"], {})
                decision = decide(
                    claim=claim["payload"],
                    relationships=claim_rels,
                    sources_by_url=sources_by_url,
                    temporal_signal=signal,
                )
                verdict_row = Verdict(
                    session_id=session.id,
                    claim_id=claim["row"].id,
                    verdict=decision["verdict"],
                    calibrated_probability=decision["calibrated_probability"],
                    evidence_quality=decision["evidence_quality"],
                    supporting_count=decision["supporting_count"],
                    contradicting_count=decision["contradicting_count"],
                    components=decision["components"],
                    explanation=decision["explanation"],
                    what_changed=decision["what_changed"],
                    limitations=decision["limitations"],
                    decided_by=decision["decided_by"],
                )
                self.db.add(verdict_row)
                verdict_rows.append(verdict_row)
            self.db.commit()

            overall_verdict, confidence = overall(
                [{"verdict": v.verdict, "evidence_quality": v.evidence_quality,
                  "calibrated_probability": v.calibrated_probability} for v in verdict_rows]
            )
            distribution: dict[str, int] = {}
            for v in verdict_rows:
                distribution[v.verdict] = distribution.get(v.verdict, 0) + 1
            _mark(
                session.stage_states, Stage.GENERATING_VERDICTS, "done",
                detail=f"{len(verdict_rows)} verdicts · overall {overall_verdict}",
                metrics={"distribution": distribution, "overall": overall_verdict},
            )
            self._sync(session)

            # ---------------- finalise -----------------------------------
            elapsed = round((time.perf_counter() - started_perf) * 1000, 2)
            self._log_model_executions(session.id)
            for call in self.gw.calls:
                if call.status in {"ok", "unparseable"} and call.provider != "deterministic":
                    cost += call.cost_usd
                    tokens += call.prompt_tokens + call.completion_tokens

            session.overall_verdict = overall_verdict
            session.confidence = confidence
            session.summary = self._summary(overall_verdict, verdict_rows, len(sources))
            session.models_used = sorted({c.model for c in self.gw.calls} | {"epoch-heuristics-v1"})
            session.metrics = {
                "runtime_mode": settings.runtime_mode,
                "llm_live": self.gw.live,
                "search_provider": retrieval_meta.get("provider"),
                "claim_count": len(claims),
                "evidence_count": len(sources),
                "relationship_count": len(relationships),
                "searches": retrieval_meta.get("searches", 0),
                "failed_searches": retrieval_meta.get("failed_searches", 0),
                "deduplicated": retrieval_meta.get("deduplicated", 0),
                "tokens": tokens,
                "estimated_cost_usd": round(cost, 6),
                "pipeline_latency_ms": elapsed,
                "verdict_distribution": distribution,
                "evidence_quality_mean": round(
                    sum(v.evidence_quality for v in verdict_rows) / max(1, len(verdict_rows)), 4
                ),
                "temporal_observations": len(observations),
            }
            session.stage = Stage.COMPLETE
            session.progress = 1.0
            session.status = "succeeded"
            session.completed_at = _now()
            self.db.commit()
            log.info(
                "research_complete",
                extra={"event": "research_complete", "research_id": session.id, "duration_ms": elapsed},
            )
            return session

        except Exception as exc:  # noqa: BLE001
            self.db.rollback()
            session = self.db.get(ResearchSession, session_id)
            if session is not None:
                failed_stage = session.stage
                states = session.stage_states or _stage_template()
                if failed_stage in STAGE_ORDER:
                    _mark(states, failed_stage, "failed", detail=str(exc)[:400])
                session.stage_states = states
                session.status = "failed"
                session.stage = Stage.FAILED
                session.error = f"{type(exc).__name__}: {exc}"[:600]
                session.completed_at = _now()
                session.progress = _progress(states)
                self.db.commit()
            log.error(
                "research_failed",
                extra={"event": "research_failed", "research_id": session_id, "extra_data": traceback.format_exc()[-1200:]},
            )
            raise

    # ------------------------------------------------------------------ #
    # helpers
    # ------------------------------------------------------------------ #
    def _await(self, coro):
        """Run a coroutine from sync code (works inside and outside a loop)."""
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)
        # Already inside a loop (async endpoint): run in a worker thread.
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()

    def _sync(self, session: ResearchSession) -> None:
        # JSON columns need an explicit dirty flag: stage_states is mutated in place.
        session.stage_states = [dict(state) for state in (session.stage_states or [])]
        flag_modified(session, "stage_states")
        session.progress = _progress(session.stage_states or [])
        self.db.commit()

    def _persist_claim(self, session: ResearchSession, claim: dict) -> dict:
        row = Claim(
            session_id=session.id,
            ordinal=claim["ordinal"],
            text=claim["text"],
            normalized=claim["normalized"],
            claim_type=claim["claim_type"],
            entities=claim["entities"],
            numbers=claim["numbers"],
            dates=claim["dates"],
            versions=claim["versions"],
            checkworthiness=claim["checkworthiness"],
            search_queries=[],
            parent_claim_id=claim.get("parent_claim_id"),
            extracted_by=claim["extracted_by"],
        )
        self.db.add(row)
        self.db.commit()
        payload = {**claim, "id": row.id, "search_queries": []}
        return {"row": row, "payload": payload}

    def _persist_sources(self, session: ResearchSession, sources: list[dict]) -> dict[str, EvidenceSource]:
        persisted: dict[str, EvidenceSource] = {}
        for source in sources:
            row = EvidenceSource(
                session_id=session.id,
                url=source["url"],
                canonical_url=source["canonical_url"],
                domain=source["domain"],
                title=source["title"],
                publisher=source.get("publisher"),
                source_type=source["source_type"],
                published_at=source.get("published_at"),
                effective_at=source.get("effective_at"),
                retrieved_at=source["retrieved_at"],
                authority_score=source["authority_score"],
                freshness_score=source.get("freshness_score", 0.5),
                content=source["content"],
                raw_metadata=source.get("raw_metadata", {}),
                injection_flags=source.get("injection_flags", []),
                dedupe_key=source["dedupe_key"],
                provider=settings.runtime_mode,
                version=source.get("version"),
                supersedes=source.get("supersedes"),
            )
            self.db.add(row)
            persisted[source["url"]] = row
        self.db.commit()
        return persisted

    def _apply_source_updates(self, persisted: dict[str, EvidenceSource], updates: dict[str, dict]) -> None:
        for url, change in updates.items():
            row = persisted.get(url)
            if row is None:
                continue
            row.freshness_score = float(change.get("freshness_score", row.freshness_score))
            row.is_superseded = bool(change.get("is_superseded", False))
        self.db.commit()

    def _persist_observations(self, session, claims, persisted_sources, observations) -> None:
        claim_by_text = {c["payload"]["text"]: c["row"] for c in claims}
        for obs in observations:
            claim_row = claim_by_text.get(obs["claim_key"])
            if claim_row is None:
                continue
            source_row = persisted_sources.get(obs.get("source_url") or "")
            self.db.add(
                TemporalObservation(
                    session_id=session.id,
                    claim_id=claim_row.id,
                    source_id=source_row.id if source_row else None,
                    observation_type=obs["observation_type"],
                    detail=obs["detail"],
                    published_at=obs.get("published_at"),
                    effective_at=obs.get("effective_at"),
                    retrieved_at=obs.get("retrieved_at"),
                    age_days=obs.get("age_days"),
                    decay_factor=obs.get("decay_factor"),
                    payload=obs.get("payload", {}),
                )
            )
        self.db.commit()

    def _persist_relationships(self, session, claims, persisted_sources, relationships) -> None:
        claim_by_text = {c["payload"]["text"]: c["row"] for c in claims}
        for rel in relationships:
            claim_row = claim_by_text.get(rel["claim_key"])
            source_row = persisted_sources.get(rel["source_url"])
            if claim_row is None or source_row is None:
                continue
            passage = EvidencePassage(
                source_id=source_row.id,
                claim_id=claim_row.id,
                text=tu.truncate(rel.get("passage_text", ""), 1200),
                relevance=float(rel.get("relevance", 0.0)),
            )
            self.db.add(passage)
            self.db.flush()
            self.db.add(
                ClaimEvidenceRelationship(
                    claim_id=claim_row.id,
                    source_id=source_row.id,
                    passage_id=passage.id,
                    stance=rel["stance"],
                    strength=float(rel["strength"]),
                    rationale=rel["rationale"],
                    conflict_kind=rel.get("conflict_kind"),
                    is_resolved=False,
                )
            )
        self.db.commit()

    def _log_model_executions(self, session_id: str) -> None:
        for call in self.gw.calls:
            self.db.add(
                ModelExecutionLog(
                    session_id=session_id,
                    provider=call.provider,
                    model=call.model,
                    task="gateway",
                    route=call.route,
                    status=call.status,
                    latency_ms=call.latency_ms,
                    prompt_tokens=call.prompt_tokens,
                    completion_tokens=call.completion_tokens,
                    cost_usd=call.cost_usd,
                    retries=call.retries,
                    error=call.error,
                )
            )
        self.db.commit()

    def _summary(self, overall_verdict: str, verdicts, evidence_count: int) -> str:
        counts: dict[str, int] = {}
        for v in verdicts:
            counts[v.verdict] = counts.get(v.verdict, 0) + 1
        parts = [f"{n} {name.replace('_', ' ').lower()}" for name, n in sorted(counts.items(), key=lambda kv: -kv[1])]
        changed = [v for v in verdicts if v.what_changed]
        summary = (
            f"Analysed {len(verdicts)} claims against {evidence_count} unique sources. "
            f"Overall verdict: {overall_verdict.replace('_', ' ')}. "
            f"Distribution: {', '.join(parts)}."
        )
        if changed:
            summary += " " + changed[0].what_changed
        if any(v.verdict == VerdictEnum.UNVERIFIED.value for v in verdicts):
            summary += " Some claims could not be certified from the available evidence."
        return summary
