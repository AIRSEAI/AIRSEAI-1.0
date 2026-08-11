#!/usr/bin/env bash
set -euo pipefail

ROOT="${EMBODICORE_ROOT:-$HOME/workspace/AIRSEAI-EmbodiCore}"
REPO="${MAMBA_POLICY_REPO:-$ROOT/third_party/Mamba-Policy}"
OUT="$ROOT/part2_results"
GPU_ID="${GPU_ID:-0}"
TRACE_COUNT="${TRACE_COUNT:-1000}"
MIXER_TRACE_COUNT="${MIXER_TRACE_COUNT:-64}"
STALE_PAIRS="${STALE_PAIRS:-100}"

cd "$ROOT"

if [[ -z "${CHECKPOINT:-}" ]]; then
  echo "CHECKPOINT is not set. Searching official output directories..."
  set +e
  SEARCH_OUTPUT="$(python part2/find_checkpoint.py --repo "$REPO")"
  SEARCH_RC=$?
  set -e
  echo "$SEARCH_OUTPUT"
  if [[ $SEARCH_RC -ne 0 ]]; then
    echo
    echo "STOP: NEED_CHECKPOINT"
    echo "Set CHECKPOINT=/absolute/path/to/a/real/Mamba-Policy/.ckpt and rerun."
    exit 20
  fi
  CHECKPOINT="$(echo "$SEARCH_OUTPUT" | sed -n 's/^AUTO_SELECTED=//p')"
fi

rm -rf "$OUT"
mkdir -p "$OUT"

python part2/preflight.py \
  --repo "$REPO" \
  --checkpoint "$CHECKPOINT" \
  --out "$OUT"

python part2/source_audit.py \
  --repo "$REPO" \
  --out "$OUT"

python part2/collect_real_traces.py \
  --repo "$REPO" \
  --checkpoint "$CHECKPOINT" \
  --out "$OUT" \
  --trace-count "$TRACE_COUNT" \
  --mixer-trace-count "$MIXER_TRACE_COUNT" \
  --stale-pairs "$STALE_PAIRS" \
  --paper-action-steps 3 \
  --gpu "$GPU_ID" | tee "$OUT/collector_stdout.txt"

python part2/package_results.py \
  --repo "$REPO" \
  --out "$OUT" \
  --zip "$ROOT/part2_real_traces.zip"

echo
echo "============================================================"
echo "DONE — PART II PASS"
echo "Upload this file:"
echo "$ROOT/part2_real_traces.zip"
echo "============================================================"
