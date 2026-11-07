# API reference (v1)

Base URL: `/api/v1` · Interactive docs: `/api/docs` · OpenAPI: `/api/openapi.json`

All responses are JSON. Errors are uniform:

```json
{ "error": { "code": "validation_error", "message": "Request validation failed.",
             "details": [...], "request_id": "9f3c1e0a7b2d4f18" } }
```

| Code | HTTP | Meaning |
|---|---|---|
| `validation_error` | 422 | Pydantic validation / size violation |
| `not_found` | 404 | Unknown research id |
| `unsafe_url` | 400 | SSRF/URL validation rejected the input |
| `rate_limited` | 429 | Sliding-window limit exceeded (`retry_after` in details) |
| `provider_error` | 502 | Upstream model/search provider failed |
| `payload_too_large` | 413 | Body exceeds 4× the input cap |
| `internal_error` | 500 | Unhandled server error (logged with the same request id) |

Rate limit: `RATE_LIMIT_PER_MINUTE` per client+route (default 60).

---

## POST /claims/preview

Extract claims without running research. No persistence, no retrieval budget.

```bash
curl -X POST localhost:8000/api/v1/claims/preview -H 'content-type: application/json' \
  -d '{"content":"Python 3.7 is the newest version of Python. React 19 shipped in December 2024."}'
```

```json
{
  "claims": [{"text":"Python 3.7 is the newest version of Python","claim_type":"version",
              "entities":["Python"],"numbers":["3.7"],"dates":[],"versions":["3.7"],
              "checkworthiness":0.9,"ordinal":0,"extracted_by":"heuristic/v1"}],
  "meta": {"method":"heuristic","provider":"deterministic","count":2,"time_sensitive":2,"runtime_mode":"simulated"}
}
```

## POST /research

```json
{ "content": "Python 3.7 is the newest version of Python and should be used for all new projects.",
  "input_type": "text",        // text | ai_answer | url
  "depth": "standard",         // quick | standard | deep
  "title": "optional",
  "run_synchronously": false }
```

`201` → `{"research_id":"rs_…","status":"queued","runtime_mode":"simulated","poll_url":"/api/v1/research/rs_…"}`

For `input_type=url` the target is fetched only after `validate_public_url` (scheme allow-list, no credentials,
no private/loopback/link-local targets), size-capped and reduced to text.

## GET /research/{id}

Returns the session with **real** `stage_states` (each `pending|running|done|failed` plus `started_at`,
`finished_at`, `duration_ms`, `detail`, `metrics`), `progress`, `metrics` and, once succeeded, `claims[]` with
verdicts and evidence references.

## GET /research/{id}/evidence

```json
{ "research_id":"rs_…", "sources":[…], "temporal_observations":[…], "claims":[…],
  "graph": { "nodes":[{"id":"clm_…","kind":"claim","label":"…","verdict":"OUTDATED"}, …],
             "links":[{"source":"clm_…","target":"src_…","stance":"contradicts","strength":0.83}],
             "counts":{"claims":3,"sources":10,"supports":2,"contradicts":4,"temporal":7} } }
```

Node kinds: `claim`, `source`, `temporal`. Link stances: `supports`, `contradicts`, `supersedes`,
`context_only`, `temporal`.

## GET /research/{id}/report

Overall verdict + confidence, per-claim verdict objects (`explanation`, `what_changed`, `limitations`,
`components`), cited sources with `published_at`/`retrieved_at`, temporal observations, metrics, aggregated
limitations and the calibration note.

## GET /history

Query params: `q`, `verdict`, `status`, `date_from`, `date_to` (ISO 8601), `limit` (1–100), `offset`.
Returns `{total, limit, offset, items[]}`.

## GET /analytics

`totals` (sessions, completed, failed, claims_analyzed, sources_retrieved, outdated_detected, verdicts_issued),
`verdict_distribution`, `claim_type_distribution`, `quality`, `performance`, 14-day `activity`, `top_domains`,
`recent`, `benchmarks`.

## GET /system/health

`status`, `runtime_mode` (+`mode_explanation`), `database`, `providers{configured}`, `model_routing{primary,
fallback, chain, gateway}`, `python`, `limits`.

## GET /system/observability

`by_model[]` (provider, model, route, status, calls, mean_latency_ms, tokens, cost, retries), `usage`,
`search{requests, failed_requests}`, `research{by_status, mean_execution_ms, verification_failures}`,
`stage_latency_ms`, and `notes` describing exactly how the numbers are aggregated.

## GET /benchmark/latest

The latest measured run: `epoch` / `baseline` metric maps, `delta`, `per_class`, `confusion`, `calibration`,
`notes`, and `examples[]` — correct predictions with real claims, verdicts and citation URLs.
`{"available": false, "message": "…"}` until `run_benchmark.py` has been executed.
