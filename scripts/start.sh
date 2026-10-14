#!/usr/bin/env bash
set -euo pipefail
mycut_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$mycut_root"
mycut_python="${MYCUT_PYTHON:-$mycut_root/.venv-app/bin/python}"
[[ -x "$mycut_python" ]] || { echo 'Prepare .venv-app conforme o README, ou informe MYCUT_PYTHON.' >&2; exit 1; }
[[ -f web/dist/index.html ]] || { echo 'Compile a interface: cd web && pnpm install && npm run build' >&2; exit 1; }
export PYTHONPATH="$mycut_root/backend${PYTHONPATH:+:$PYTHONPATH}"
mycut_worker_pid=''
mycut_api_pid=''
cleanup() {
  [[ -z "$mycut_worker_pid" ]] || kill "$mycut_worker_pid" 2>/dev/null || true
  [[ -z "$mycut_api_pid" ]] || kill "$mycut_api_pid" 2>/dev/null || true
  wait || true
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
"$mycut_python" -c 'import os; from mycut import store; from mycut.seed import initialize_example; store.initialize(); initialize_example() if os.environ.get("MYCUT_SEED", "1") == "1" else None'
"$mycut_python" -m mycut.worker &
mycut_worker_pid=$!
"$mycut_python" -m uvicorn mycut.api:app --host 127.0.0.1 --port 8321 &
mycut_api_pid=$!
printf 'MyCut: http://localhost:8321\n'
wait -n "$mycut_worker_pid" "$mycut_api_pid"
