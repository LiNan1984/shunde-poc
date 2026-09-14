#!/usr/bin/env bash
# Load KEY=VALUE secret files without overriding existing env or executing values.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SECRET_DIR="${QWENPAW_SECRET_DIR:-${HOME}/.qwenpaw.secret}"

_load_env_file() {
  local file="$1" line key value
  [[ -f "$file" ]] || return 0
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"
    case "$line" in
      ''|\#*) continue ;;
    esac
    [[ "$line" == *=* ]] || continue
    key="${line%%=*}"
    value="${line#*=}"
    key="${key// /}"
    if [[ "$value" == \"*\" && "$value" == *\" ]]; then
      value="${value:1:${#value}-2}"
    elif [[ "$value" == \'*\' && "$value" == *\' ]]; then
      value="${value:1:${#value}-2}"
    fi
    [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
    if [[ -z "${!key+x}" ]]; then
      export "${key}=${value}"
    fi
  done < "$file"
}

_load_env_file "${SECRET_DIR}/middleware.env"
_load_env_file "${SECRET_DIR}/embedding.env"
export PYTHONPATH="${PYTHONPATH:-}:${ROOT}"
exec "${ROOT}/.venv/bin/python" -m poc.kb_mcp "$@"
