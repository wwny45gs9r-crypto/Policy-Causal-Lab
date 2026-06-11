#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

if [[ -x "$BACKEND_DIR/.venv/bin/python" ]]; then
  PYTHON="$BACKEND_DIR/.venv/bin/python"
else
  PYTHON="${PYTHON:-python3}"
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "npm was not found. Install Node.js 20+ before starting the frontend." >&2
  exit 1
fi

if ! "$PYTHON" -c "import uvicorn" >/dev/null 2>&1; then
  echo "Backend dependencies are missing. Run: cd backend && pip install -r requirements.txt" >&2
  exit 1
fi

if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
  echo "Frontend dependencies are missing. Run: cd frontend && npm install" >&2
  exit 1
fi

cleanup() {
  [[ -z "${BACKEND_PID:-}" ]] || kill "$BACKEND_PID" 2>/dev/null || true
  [[ -z "${FRONTEND_PID:-}" ]] || kill "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

(
  cd "$BACKEND_DIR"
  "$PYTHON" -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
) &
BACKEND_PID=$!

(
  cd "$FRONTEND_DIR"
  npm run dev
) &
FRONTEND_PID=$!

echo "Frontend: http://localhost:3000"
echo "FastAPI:  http://localhost:8000"
echo "Docs:     http://localhost:8000/docs"
echo "Hello:    http://localhost:3000/api/hello"
wait
