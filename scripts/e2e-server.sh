#!/usr/bin/env bash
set -euo pipefail
mycut_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
mycut_test_data="$(mktemp -d -t mycut-e2e-XXXXXXXX)"
export MYCUT_DATA_DIR="$mycut_test_data" MYCUT_SEED=0
mycut_server_pid=''
cleanup() {
  [[ -z "$mycut_server_pid" ]] || kill "$mycut_server_pid" 2>/dev/null || true
  wait || true
  rm -rf -- "$mycut_test_data"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
bash "$mycut_root/scripts/start.sh" &
mycut_server_pid=$!
wait "$mycut_server_pid"
