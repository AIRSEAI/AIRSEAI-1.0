#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

python3 scripts/verify_release.py

if [ -f hardware/pg2k400/pre_handoff/MANIFEST.sha256 ]; then
  (
    cd hardware/pg2k400/pre_handoff
    shasum -a 256 -c MANIFEST.sha256 >/dev/null
  )
  echo "  FPGA pre-handoff manifest: PASS"
else
  echo "  FAIL: missing FPGA pre-handoff manifest" >&2
  exit 1
fi

if [ -f MANIFEST.sha256 ]; then
  shasum -a 256 -c MANIFEST.sha256 >/dev/null
  echo "  Release manifest: PASS"
fi

if command -v iverilog >/dev/null 2>&1; then
  TMP="$(mktemp -t embodicore_v7).vvp"
  iverilog -g2012 -o "$TMP" \
    rtl/embodicore_semantic_controller.sv \
    rtl/embodicore_condition_ingress.sv \
    rtl/embodicore_pg_selftest_top.sv \
    rtl/testbench/tb_pg_selftest.sv
  vvp "$TMP" >/dev/null
  rm -f "$TMP"
  echo "  PG self-test RTL compile/run: PASS"
else
  echo "  PG self-test RTL compile/run: SKIPPED (iverilog not installed)"
fi

echo
echo "EMBODICORE CAL CLAIM-AUDIT ARTIFACT: PASS"
