# Deployment

Both target flows below are **free-tier first**, and both keep every credential server-side.

## Option A — Render (single service, recommended)

One Docker image serves the API *and* the built React SPA on the same origin, so there is no CORS surface and no
second host to configure.

1. Push the repository to GitHub.
2. Render → **New → Blueprint** → select the repo (`render.yaml` is auto-detected).
3. Set the secret env vars in the Render dashboard (`sync: false` placeholders):
   `BIFROST_API_KEY`, `BIFROST_BASE_URL`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `TAVILY_API_KEY`.
4. Deploy. Health check: `/api/v1/system/health` (already wired in the blueprint).
5. Optional Neon: replace `DATABASE_URL` with the Neon connection string
   (`postgresql+psycopg://…?sslmode=require`). Without it the service runs on SQLite and the free instance's disk
   is ephemeral — fine for a demo, not for persistence.

Build locally exactly as Render does:

```bash
docker build -t epoch-ai .
docker run -p 8000:8000 -e TAVILY_API_KEY=… -e OPENAI_API_KEY=… epoch-ai
open http://localhost:8000
```

## Option B — Vercel (frontend) + Render (API)

1. Deploy the API to Render (Option A, but without the SPA).
2. Edit `vercel.json`: replace `YOUR-RENDER-SERVICE.onrender.com` in the `/api/:path*` rewrite.
3. Vercel → **New Project** → import the repo. The config sets `cd frontend && npm run build`, output `frontend/dist`.
4. Add nothing else — the browser calls `/api/*` on the Vercel domain and the rewrite proxies it to Render, so keys
   never reach the client and no CORS config is needed.

## Option C — Docker Compose with Postgres + pgvector

```bash
export TAVILY_API_KEY=… OPENAI_API_KEY=…
docker compose up --build
# API + SPA → http://localhost:8000
# Postgres  → localhost:5432 (user/pass/db: epoch)
```

`app/db/pgvector.py` enables the `vector` extension, adds `embedding_vec vector(1536)` to `evidence_passages` and
creates an IVFFlat cosine index on startup. If the extension is unavailable the app logs a warning and continues
with JSON-embedded arrays — pgvector is an accelerator, never a hard dependency.

## Environment matrix

| Variable | Required | Default | Notes |
|---|---|---|---|
| `DATABASE_URL` | no | `sqlite:///./epoch.db` | Use `postgresql+psycopg://…` in production |
| `TAVILY_API_KEY` | for live search | — | Absent ⇒ bundled corpus (simulated mode) |
| `BIFROST_API_KEY` / `BIFROST_BASE_URL` | for live models | — | Preferred gateway (OpenAI-compatible) |
| `OPENAI_API_KEY` | alternative | — | Used when Bifrost is not configured |
| `GEMINI_API_KEY` | alternative | — | Used when neither is configured |
| `MODEL_PRIMARY` / `MODEL_FALLBACK` | no | `openai/gpt-4o-mini` / `google/gemini-2.0-flash` | Fallback chain |
| `CORS_ORIGINS` | no | localhost dev origins | Comma separated; unnecessary in Option A |
| `RATE_LIMIT_PER_MINUTE` | no | 60 | Lower it on public demos |
| `MAX_INPUT_CHARS` | no | 20000 | Hard cap, enforced twice |
| `ALLOW_PRIVATE_NETWORKS` | no | false | Keep false in production (SSRF guard) |
| `PRICE_INPUT_PER_1K` / `PRICE_OUTPUT_PER_1K` / `TAVILY_PRICE_PER_SEARCH` | no | small defaults | Only affects cost *estimation* |
| `ENVIRONMENT` | no | `local` | `production` in deploys |

## Production checklist

- [ ] `ALLOW_PRIVATE_NETWORKS=false`, `ENVIRONMENT=production`, real `CORS_ORIGINS`.
- [ ] Secrets set in the platform dashboard, never in `.env` committed to git (`.gitignore` covers `.env*`).
- [ ] `RATE_LIMIT_PER_MINUTE` reduced for public access.
- [ ] Postgres with backups if reports must survive restarts (SQLite on free tiers is ephemeral).
- [ ] `python -m pytest tests -q` green and `run_benchmark.py` executed so the landing page shows real numbers.
- [ ] Logs shipping (JSON structured logs already include `request_id`, `research_id`, `duration_ms`).

## Cost notes (free-tier orientation)

- **Deterministic mode costs nothing**: no provider calls at all (verified: observability reports 0 tokens/cost).
- **Live mode** cost per investigation ≈ `claims × queries × tavily_price` + model tokens at your contract prices.
  The observability page computes the estimate from the prices you configure; it never invents a figure.
- Recommended demo posture: deterministic mode by default, live mode enabled deliberately for a judge walkthrough.
