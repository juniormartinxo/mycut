#!/usr/bin/env bash
set -euo pipefail
mycut_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$mycut_root"
export PYTHONPATH="$mycut_root/backend${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m mycut.agent_runner
