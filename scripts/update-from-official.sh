#!/usr/bin/env bash
# Pull official QwenPaw (agentscope-ai/QwenPaw) into the submodule.
# Our POC stays in poc/ — do not patch QwenPaw kernel.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .gitmodules ]] || ! grep -q 'path = QwenPaw' .gitmodules; then
  echo "QwenPaw is not registered as a submodule. See docs/前端四助手交接文档.md" >&2
  exit 1
fi

git submodule update --init --remote QwenPaw
git -C QwenPaw fetch origin
git -C QwenPaw status -sb
echo
echo "Official HEAD: $(git -C QwenPaw rev-parse --short HEAD) $(git -C QwenPaw log -1 --format=%s)"
echo "Parent repo still pins the previous SHA until you:"
echo "  git add QwenPaw && git commit -m 'chore: bump QwenPaw submodule from official'"
