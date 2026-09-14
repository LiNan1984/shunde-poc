#!/usr/bin/env bash
# Start official MinerU FastAPI (opendatalab/MinerU) on 127.0.0.1:18000.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MINERU_DIR="$ROOT/MinerU"
VENV="$MINERU_DIR/.venv"
if [[ ! -x "$VENV/bin/mineru-api" ]]; then
  echo "MinerU not installed. Clone+install first:" >&2
  echo "  git clone --depth 1 https://github.com/opendatalab/MinerU.git \"$MINERU_DIR\"" >&2
  echo "  uv venv \"$VENV\" && uv pip install -e \"$MINERU_DIR[core]\" --python \"$VENV/bin/python\"" >&2
  exit 1
fi
export MINERU_API_OUTPUT_ROOT="${MINERU_API_OUTPUT_ROOT:-$ROOT/.cache/mineru-api}"
mkdir -p "$MINERU_API_OUTPUT_ROOT"
echo "MINERU_ENDPOINT=http://127.0.0.1:18000"
exec "$VENV/bin/mineru-api" --host 127.0.0.1 --port 18000
