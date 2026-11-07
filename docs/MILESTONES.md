# Build log

Milestone-by-milestone record: what was built, where it lives, the commands used, and what verified it.
Only work that is actually in the repository is listed.

---

## M1 — Foundation & contracts

**Files:** `backend/requirements.txt`, `backend/app/main.py`, `backend/app/core/{config,logging,errors,ratelimit,security}.py`,
`backend/app/schemas/{enums,research,evidence}.py`, `backend/app/db/{models,session,seed}.py`

- FastAPI app with lifespan DB init, CORS, request-id middleware, JSON structured logs, 413 body guard, uniform
  error envelope, rate limiter, `GET /api/v1/meta`.
- 10 tables defined in SQLAlchemy 2.0: `users`, `research_sessions`, `claims`, `evidence_sources`,
  `evidence_passages`, `claim_evidence_relationships`, `temporal_observations`, `verdicts`, `model_execution_logs`,
  `benchmark_results`.
- Security primitives: `sanitize_text`, `detect_prompt_injection`, `fence_untrusted`, `validate_public_url` (SSRF).

**Verify:** `python -m pytest tests -q` · `curl localhost:8000/api/v1/meta`

## M2 — Claims, planning, retrieval

**Files:** `app/services/research/{textutil,claim_extraction,planner,retrieval}.py`, `corpus.json`,
`app/services/llm/{gateway,prompts}.py`

- Heuristic claim splitter (sentence boundaries, " and "-clause handling, self-containment filter), entity/date/
  number/version extraction, checkworthiness scoring, claim typing (version, temporal, numeric, policy, factual).
- Planner emits deduplicated, type-aware queries per depth (`quick|standard|deep`).
- Retrieval with provider chain (Tavily → bundled corpus → fixtures), normalisation, dedupe by canonical URL,
  authority scoring, passage splitting with offsets, injection flagging.
- `LLMGateway` with Bifrost → OpenAI → Gemini → deterministic routing, retry/backoff, cost accounting, per-call
  logging into `model_execution_logs`.

**Verify:** unit tests for extraction/planning/retrieval; `POST /api/v1/claims/preview`.

## M3 — Temporal intelligence

**Files:** `app/services/research/temporal.py`

- Publication vs. effective date separation, half-life decay per claim type (version 210 d, numeric 420 d,
  temporal 300 d, policy 540 d, factual 1460 d), primary-source freshness floor 0.62 for stable factual claims.
- Version drift detection with entity anchoring, numeric drift with `_strip_dates`, same-unit and >2 % deviation
  gates, expiry/supersession detection.
- Emits `temporal_observations` rows consumed by the evidence explorer and the report.

## M4 — Contradictions & verdicts

**Files:** `app/services/research/{contradiction,scoring,verdict}.py`, `calibration.json`

- Pair classifier producing `supports | contradicts | supersedes | context_only` with typed conflict kinds
  (`numeric`, `date`, `version`, `polarity`, `scope`, `superseded`) plus polarity classification
  (neutral / affirmation / denial / cessation) and `superseded_overlap` gating.
- Subject/entity gate so evidence about a different subject is context, never a refutation.
- Evidence quality vs. calibrated probability kept strictly separate; `UNVERIFIED` capped at 0.5 by design.
- `decide()` implements the full decision table documented in `ARCHITECTURE.md §5`.

## M5 — Pipeline, jobs, reports, API

**Files:** `app/services/research/{pipeline,jobs,report}.py`, `app/api/v1/{claims,research,history,analytics,system}.py`

- Six-stage pipeline writing real `stage_states` (started/finished/duration/detail/metrics) with `flag_modified`
  persistence; failures stored on the session rather than swallowed.
- Background dispatch via `asyncio.to_thread` with timeout; optional synchronous execution for tests/CI.
- Report builder: per-claim verdict narrative, `what_changed`, limitations, provenance numbering, calibration note.
- Endpoints: `claims/preview`, `research` (POST/GET), `evidence`, `report`, `history`, `analytics`,
  `system/health`, `system/observability`.

**Verify:** `pytest tests/test_api.py` — full lifecycle, 404 paths, validation errors, report/evidence consistency.

## M6 — Benchmark harness & measurement

**Files:** `backend/benchmark/{build_dataset.py,dataset.jsonl,run_benchmark.py}`, `benchmark/results/`,
`app/api/v1/benchmark.py`

- 19 real fact families × 6 variants → **114 labelled claims** across the five required categories (+ partial and
  second-shape contradiction rows). Labels from construction semantics, never from engine output.
- Harness measures accuracy, macro P/R/F1, per-class, outdated recall, citation correctness, coverage, false
  verification, latency and cost; runs the pipeline against an **isolated temp DB** so results never touch app data.
- Baseline system (LLM-only style single-snippet judgement) for comparison; `--persist` writes
  `benchmark_results` rows and `--fit-calibration` refits `calibration.json`.
- `GET /api/v1/benchmark/latest` exposes the artefact with real correct examples for the landing page.

**Verify:** `python benchmark/run_benchmark.py --persist --fit-calibration`
→ accuracy **0.825**, macro F1 **0.824**, outdated recall **0.871**, false-verification **0.182**, citation **1.000**.

Errors found and fixed during this milestone are listed in §11.

## M7 — React frontend

**Files:** `frontend/src/{main.tsx,App.tsx,index.css}`, `lib/{api.ts,verdicts.ts,format.ts,theme.tsx}`,
`components/{ui,AppShell,PipelineTimeline,EvidenceGraph}.tsx`, `pages/{Landing,Dashboard,Workspace,EvidenceExplorer,ReportPage,HistoryPage,SystemPage}.tsx`

- Typed API client mirroring the Pydantic schemas; theme provider (dark/light, persisted); 7 pages wired with
  React Router; print stylesheet for the report.
- Workspace polls at 800 ms and renders persisted stage states; Evidence Explorer lays out a deterministic
  3-column SVG graph with an inspector; Report supports Copy-Markdown, JSON and Markdown download, and Print/PDF.
- No fabricated data: empty states and simulated-mode labels everywhere a live figure would be expected.

**Verify:** `npx tsc --noEmit` clean · `npm run build` → `dist/` (`index-*.js` ≈ 843 kB, gzip ≈ 241 kB).

## M8 — Hardening passes

- Benchmark DB isolation (`tempfile.mkdtemp()` before app imports) — fixed a 915-session pollution incident.
- `polarity_relation` + `superseded_overlap` window fix + entity subject gate — resolved a false COVID/WHO
  contradiction *without* the accuracy collapse the first attempt caused (0.816 → 0.719 → **0.825**).
- 22 tests green after every change; `pytest tests -q` is the gate before any benchmark run.

## M9 — Docs, deployment, pgvector

**Files:** `README.md`, `docs/{ARCHITECTURE,API,BENCHMARK,DEPLOYMENT,MILESTONES}.md`, `.env.example`, `.gitignore`,
`Dockerfile`, `backend/Dockerfile`, `docker-compose.yml`, `render.yaml`, `vercel.json`, `Makefile`,
`backend/app/db/pgvector.py`

- Single-image build (SPA + API), Render blueprint with health check, Vercel rewrite config, compose stack with
  `pgvector/pgvector:pg16`.
- Optional pgvector: extension + `embedding_vec` column + IVFFlat index at startup, non-fatal fallback.
- Honest limitations published next to the numbers.

---

## 9. Commands that reproduce the whole build

```bash
# backend
cd backend && pip install -r requirements.txt
python -m pytest tests -q                              # 22 passed
python benchmark/build_dataset.py                      # 114 claims
python benchmark/run_benchmark.py --persist --fit-calibration
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# frontend
cd ../frontend && npm install
npx tsc --noEmit && npm run build

# stack
cd .. && docker compose up --build     # API + SPA + Postgres/pgvector
```

## 10. Test inventory (22)

| Area | Tests |
|---|---|
| Text/claims | splitter determinism, self-containment, entity/version extraction, checkworthiness ordering |
| Retrieval | provider fallback, dedupe, authority ranking, passage offsets |
| Temporal | half-life decay, version drift anchoring, numeric tolerance, expiry signalling |
| Contradiction | support/deny polarity, supersession overlap, subject gate, numeric conflict |
| Verdict/scoring | UNVERIFIED cap, VERIFIED evidence requirement, CONFLICTING vs OUTDATED |
| API | full lifecycle, sync + async, evidence/report shape, 404, validation, rate limit, SPA serving |

## 11. Errors hit and how they were fixed

| Problem | Fix |
|---|---|
| JSON stage mutations lost | `flag_modified` on the session column |
| Dates/unrelated figures flagged as numeric conflicts | `_strip_dates` + same-unit + >2 % deviation |
| Version drift citing unrelated versions | entity anchoring in `temporal.py` |
| Supersession misread as contradiction | `superseded_overlap` gate comparing claim terms against the supersession object window |
| Stable RFC claims reported UNVERIFIED | primary-source freshness floor 0.62 |
| Fixture lookup misses | `retrieval._match` key normalisation at 0.45 threshold |
| Template-generated dataset rows | hand-written claims; self-containment filter |
| Partial rows collapsing to OUTDATED | distinct `/support-window` URLs |
| Dead supersession branch in `decide()` | branch order rewritten; PARTIALLY_OUTDATED before OUTDATED |
| Coverage 0.833 artefact | insufficient-evidence excluded from the denominator |
| Benchmark `--persist` polluting app DB (915 sessions) | isolated temp DB before app imports |
| Cessation evidence read as contradiction; naive fix dropped accuracy to 0.719 | `polarity_relation` + window measured *after* the cue + subject/entity gate → 0.825 |
| React 19 claim contradicted by a PostgreSQL page | subject gate rejects mismatched-subject evidence |

## 12. Deliberate deviations from the spec

| Spec | Implementation | Why |
|---|---|---|
| Postgres + pgvector required | SQLite default, Postgres optional with pgvector acceleration | zero-config local/test runs; same models either way |
| Live Tavily + LLM required | deterministic offline engines when no keys | tests/benchmarks must be reproducible and free; live mode fully implemented |
| LLM-only baseline as a separate service | in-harness baseline function | keeps comparison on identical fixtures with no extra spend |
| Auth | single seeded analyst account, `user_id` on sessions | auth was out of scope; schema is ready for it |
