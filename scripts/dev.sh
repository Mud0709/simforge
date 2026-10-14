#!/usr/bin/env bash
# Run backend (http://127.0.0.1:8000) and frontend (http://localhost:3000) together.
set -euo pipefail
cd "$(dirname "$0")/.."

trap 'kill 0' EXIT INT TERM
(cd backend && uv run uvicorn simforge.main:app --reload --host 127.0.0.1 --port 8000) &
(cd frontend && npm run dev) &
wait
