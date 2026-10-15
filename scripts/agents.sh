#!/usr/bin/env bash
set -euo pipefail
mycut_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$mycut_root"
export PYTHONPATH="$mycut_root/backend${PYTHONPATH:+:$PYTHONPATH}"
# User services do not inherit a terminal's WSL interop socket. This alias is
# maintained by WSL across boots, unlike the per-session socket paths.
if [[ ! -S "${WSL_INTEROP:-}" && -S /run/WSL/1_interop ]]; then
  export WSL_INTEROP=/run/WSL/1_interop
fi
exec "${MYCUT_PYTHON:-python3}" -u -m mycut.agent_runner
