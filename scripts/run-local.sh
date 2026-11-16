#!/usr/bin/env bash
set -euo pipefail

# Keep AutoEarn AI private to this computer. Do not bind to 0.0.0.0.
HOST="127.0.0.1"
PORT="${AUTOEARN_PORT:-8000}"

if [[ ! -d ".venv" ]]; then
  echo "Create the virtual environment first: python3 -m venv .venv"
  exit 1
fi

source .venv/bin/activate
exec python -m uvicorn app.main:app --host "$HOST" --port "$PORT"
