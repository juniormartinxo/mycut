#!/usr/bin/env bash
set -euo pipefail
mycut_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
mycut_python="${MYCUT_PYTHON:-$mycut_root/.venv-app/bin/python}"
[[ -x "$mycut_python" ]] || { echo 'Prepare .venv-app conforme o README, ou informe MYCUT_PYTHON.' >&2; exit 1; }
exec "$mycut_python" "$mycut_root/scripts/launch.py" local "$@"
