#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# EPOCH AI — preview resume / bootstrap
#
# Sandbox rule: only source files persist between sessions. Installed Python
# packages, node_modules and the Vite build output (dist/) are wiped, so this
# script repairs whatever is missing and then serves the app on port 8000.
#
#   ./scripts/resume_preview.sh          # repair what's missing, then serve
#   ./scripts/resume_preview.sh --check  # repair + verify only, do not serve
#   ./scripts/resume_preview.sh --force  # reinstall and rebuild everything
# ---------------------------------------------------------------------------
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
PORT="${PORT:-8000}"
MODE="${1:-serve}"

step() { printf '\n\033[36m==> %s\033[0m\n' "$*"; }
ok()   { printf '    \033[32m%s\033[0m\n' "$*"; }

if [[ "$MODE" == "--force" ]]; then
  step "Forcing reinstalls"
  pip install -q -r "$BACKEND/requirements.txt"
  ( cd "$FRONTEND" && npm install --no-audit --no-fund >/dev/null )
  rm -rf "$FRONTEND/dist"
  ok "dependencies reinstalled, build output cleared"
fi

# 1. Python dependencies -----------------------------------------------------
step "Checking backend dependencies"
if python -c "import fastapi, sqlalchemy, uvicorn, pydantic" 2>/dev/null; then
  ok "already installed"
else
  pip install -q -r "$BACKEND/requirements.txt"
  ok "installed from backend/requirements.txt"
fi

# 2. Frontend dependencies ---------------------------------------------------
step "Checking frontend dependencies"
if [[ -d "$FRONTEND/node_modules" ]] && [[ -n "$(ls -A "$FRONTEND/node_modules" 2>/dev/null)" ]]; then
  ok "node_modules present ($(ls "$FRONTEND/node_modules" | wc -l) entries)"
else
  ( cd "$FRONTEND" && npm install --no-audit --no-fund >/dev/null )
  ok "npm install completed"
fi

# 3. Production bundle (served by FastAPI, so it must exist) -----------------
step "Checking SPA bundle"
if [[ -f "$FRONTEND/dist/index.html" ]]; then
  ok "frontend/dist present"
else
  ( cd "$FRONTEND" && npx tsc --noEmit && npm run build >/dev/null )
  ok "rebuilt frontend/dist"
fi

# 4. Tests -------------------------------------------------------------------
step "Running backend tests"
( cd "$BACKEND" && python -m pytest tests -q | tail -1 )

# 5. Serve -------------------------------------------------------------------
if [[ "$MODE" == "--check" ]]; then
  step "Repair complete (not serving; pass no flag or 'serve' to start)"
  exit 0
fi

step "Starting EPOCH AI on http://0.0.0.0:$PORT"
cd "$BACKEND"
export DATABASE_URL="${DATABASE_URL:-sqlite:///./epoch.db}"
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
