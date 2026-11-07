# Architecture

## 1. Request lifecycle

```
Browser (React SPA)
   │  POST /api/v1/research            (JSON, ≤20k chars, validated + sanitised)
   ▼
FastAPI route  ── rate limit ─► validate ─► sanitise ─► create ResearchSession (status=queued)
   │                                                   │
   │  run_synchronously=false                          └─► asyncio task (jobs.dispatch)
   ▼                                                        │
201 {research_id, poll_url}                                 ▼
   │                                       ResearchPipeline.run()   [worker thread]
   │                                          1 extraction → 2 planning → 3 retrieval
   │                                          4 temporal → 5 contradictions → 6 verdicts
   ▼                                                │ each stage: persist stage_states + metrics
GET /api/v1/research/{id}  ◄── poll ────────────────┘ progress is _derived_ from persisted states
```

The pipeline is synchronous and deterministic inside the worker thread; the API is async. `asyncio.to_thread`
keeps the event loop free, and `asyncio.wait_for` enforces `JOB_TIMEOUT_SECONDS`.

## 2. Module contracts

Every research module takes plain dicts and returns plain dicts, so each one is unit-testable without a database:

| Module | Input | Output |
|---|---|---|
| `claim_extraction.extract_claims` | text, gateway, limit | `(claims[], meta)` |
| `planner.plan_research` | claims, depth | `(plans[], meta)` |
| `retrieval.retrieve_evidence` | claims, plans, depth, fixtures | `(sources[], meta)` |
| `temporal.analyze_temporal` | claims, sources, relationships | `(observations[], source_updates, signals)` |
| `contradiction.detect_relationships` | claims, sources | `(relationships[], meta)` |
| `verdict.decide` | claim, relationships, sources, temporal signal | verdict dict |

`sources[]` normalised shape: `url, canonical_url, domain, title, publisher, source_type, published_at,
effective_at, retrieved_at, authority_score, freshness_score, content, version, raw_metadata, injection_flags,
dedupe_key`.

## 3. Provider abstraction

```
LLMGateway.complete_json(task, system, user)
   1. Bifrost (OpenAI-compatible)        if BIFROST_API_KEY
   2. OpenAI direct                      elif OPENAI_API_KEY
   3. Gemini direct                      elif GEMINI_API_KEY
   4. deterministic engine (no network)  otherwise / on failure

RetrievalProvider
   1. TavilyProvider    if TAVILY_API_KEY
   2. CorpusProvider    bundled corpus.json   (simulated mode)
   3. FixtureProvider   injected fixtures     (benchmark mode)
```

Each provider attempt is retried with exponential backoff and then falls through, so a provider outage degrades
quality instead of failing the investigation. Every call is logged to `model_execution_logs` with provider, model,
route, latency, tokens, cost, retries and status — which is what the observability page aggregates.

## 4. Scoring model

**Evidence quality** (measurement, 0–1):

```
quality = 0.30·authority + 0.22·relevance + 0.20·temporal
        + 0.18·corroboration + 0.10·consistency
```

- *authority*: mean domain authority (curated table + source-type priors).
- *relevance*: claim↔passage token coverage/overlap.
- *temporal*: mean recency weight of the sources used.
- *corroboration*: distinct supporting domains beyond the contradicting ones (saturates at 3).
- *consistency*: 1 − contradiction share of evidence weight.

Support/contradiction strength aggregate saturates: `1 − exp(−1.1 · Σ strength·authority·freshness)`, so one
strong source never looks like three.

**Recency half-lives** (days): version 210 · policy 540 · numeric 420 · temporal 300 · factual 1460. Primary
documentation (`docs`, `gov`, `paper`) for stable factual claims has a floor of 0.62 — a specification does not
expire, it gets superseded (which is detected separately).

**Calibrated probability** (prediction) is a Platt-style logistic mapping over support/contradiction/quality,
with coefficients fitted on the labelled benchmark (`app/services/research/calibration.json`). `UNVERIFIED`
bypasses the fit and is capped at 0.5 by design.

## 5. Verdict decision table

Order matters; each row is a code branch in `verdict.decide`.

| Condition | Verdict |
|---|---|
| No supporting / contradicting / superseding relation | `UNVERIFIED` |
| Temporal change (drift/expiry) **and** support quality ≥ 0.33 | `PARTIALLY_OUTDATED` |
| Temporal change, weak support | `OUTDATED` |
| Contradiction dominant; supporting evidence clearly older (≥0.75 y) | `OUTDATED` |
| Contradiction dominant, no temporal resolution | `CONTRADICTED` |
| Both sides substantive and independent; recency cannot resolve | `CONFLICTING` |
| Superseding evidence only, no real support | `OUTDATED` |
| Support survives, supersession recorded | `PARTIALLY_OUTDATED` |
| Sufficient support + independent/high-authority | `VERIFIED` |
| Support below threshold | `UNVERIFIED` |

## 6. Concurrency & persistence

- Retrieval runs per-claim with a semaphore (`RESEARCH_CONCURRENCY`), Tavily calls are independent.
- SQLite uses WAL + foreign keys; Postgres gets an optional pgvector column and IVFFlat index at startup.
- JSON columns (`stage_states`, `components`, `metrics`, `payload`) are written with explicit dirty-flagging so
  in-place mutation is never lost.
- A failed stage is recorded on the session (`status=failed`, `stage=failed`, `error`) and the failing stage's
  state is marked so the UI shows where it stopped.

## 7. Deliberate trade-offs

- **Deterministic engine instead of a mock LLM.** Tests and benchmarks exercise real logic; a mock would have made
  the benchmark numbers meaningless.
- **No force-directed graph layout.** The evidence graph is laid out deterministically by column, so a report looks
  the same every time it is opened.
- **Rule-based verdicts, not LLM verdicts.** Verdicts must be auditable and reproducible; the LLM is used for
  extraction, planning, stance and explanations, and its output is validated and merged with heuristics.
- **SQLite default.** Zero-config local runs and tests; Postgres is a first-class deployment target with the same
  models.
