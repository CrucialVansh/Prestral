#!/usr/bin/env bash
# Start backend + frontend for local development (macOS / Linux).
# Prefer two terminals if you want clearer logs — see README.md.

set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if [[ ! -f Backend/.env ]]; then
  echo "Missing Backend/.env — copy Backend/.env.example and set MISTRAL_API_KEY"
  exit 1
fi

mkdir -p Frontend
cat > Frontend/.env.local <<'EOF'
VITE_USE_MOCK=false
VITE_API_TARGET=http://localhost:8000
EOF

cleanup() {
  [[ -n "${BACKEND_PID:-}" ]] && kill "$BACKEND_PID" 2>/dev/null || true
  [[ -n "${FRONTEND_PID:-}" ]] && kill "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "Starting backend on :8000..."
(
  cd Backend
  # shellcheck disable=SC1091
  if [[ -f .venv/bin/activate ]]; then
    source .venv/bin/activate
  elif [[ -f .venv/Scripts/activate ]]; then
    source .venv/Scripts/activate
  else
    echo "No Backend/.venv — create it: python -m venv .venv && pip install -r requirements.txt"
    exit 1
  fi
  exec uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
) &
BACKEND_PID=$!

echo "Starting frontend on :5173..."
(
  cd Frontend
  [[ -d node_modules ]] || npm install
  exec npm run dev -- --host 127.0.0.1 --port 5173
) &
FRONTEND_PID=$!

echo ""
echo "  Backend:  http://localhost:8000  (docs: /docs)"
echo "  Frontend: http://localhost:5173"
echo "  Ctrl+C to stop"
echo ""
wait
