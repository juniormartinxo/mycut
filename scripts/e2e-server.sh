#!/usr/bin/env bash
set -euo pipefail
mycut_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
# MYCUT_BLOCK_TEST_DATA (under /tmp) lets the agent fixture share this instance's data and bridge.
if [[ -n "${MYCUT_BLOCK_TEST_DATA:-}" ]]; then
  mycut_test_data="$(realpath -m -- "$MYCUT_BLOCK_TEST_DATA")"
  [[ "$mycut_test_data" == /tmp/* ]] || { echo 'MYCUT_BLOCK_TEST_DATA deve ficar em /tmp.' >&2; exit 1; }
  mkdir -p -- "$mycut_test_data"
else
  mycut_test_data="$(mktemp -d -t mycut-e2e-XXXXXXXX)"
fi
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
