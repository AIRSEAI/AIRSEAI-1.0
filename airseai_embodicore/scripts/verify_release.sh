#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

python3 scripts/verify_release.py

(
  cd hardware/pg2k400/pre_handoff
  shasum -a 256 -c MANIFEST.sha256 >/dev/null
)
echo "  FPGA pre-handoff manifest: PASS"

shasum -a 256 -c MANIFEST.sha256 >/dev/null
echo "  Release manifest: PASS"

if command -v iverilog >/dev/null 2>&1; then
  TMP="$(mktemp -t embodicore_v8).vvp"
  trap 'rm -f "$TMP"' EXIT
  iverilog -g2012 -o "$TMP" \
    rtl/embodicore_semantic_controller.sv \
    rtl/embodicore_condition_ingress.sv \
    rtl/embodicore_pg_selftest_top.sv \
    rtl/testbench/tb_pg_selftest.sv
  vvp "$TMP" >/dev/null
  rm -f "$TMP"
  trap - EXIT
  echo "  PG self-test RTL compile/run: PASS"
else
  echo "  PG self-test RTL compile/run: SKIPPED (install iverilog for local RTL simulation; CI requires it)"
fi

echo
echo "EMBODICORE CAL CLAIM-AUDIT ARTIFACT: PASS"
