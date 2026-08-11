#!/usr/bin/env bash
set -eo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FAIL=0
PENDING=0

pass(){ printf '  [PASS] %s\n' "$*"; }
fail(){ printf '  [FAIL] %s\n' "$*"; FAIL=$((FAIL+1)); }
pending(){ printf '  [PENDING] %s\n' "$*"; PENDING=$((PENDING+1)); }

echo
echo "AIRSEAI EmbodiCore release verification"
echo "Target: $ROOT"
echo

# Required core
for f in README.md CITATION.cff THIRD_PARTY.md REPRODUCIBILITY.md \
         ARTIFACT_STATUS.md scripts/run_sample.sh \
         examples/minimal_semantic_contract/sample.py; do
  [ -f "$ROOT/$f" ] && pass "$f" || fail "missing required core file: $f"
done

TMP="$(mktemp)"
if (cd "$ROOT" && bash scripts/run_sample.sh) >"$TMP" 2>&1 && \
   grep -q "Semantic legality check: PASS" "$TMP"; then
  pass "minimal semantic sample"
else
  fail "minimal semantic sample"
  cat "$TMP"
fi
rm -f "$TMP"

# Optional evidence
for f in \
  results/part4/PART4_MAC_FINAL.json \
  results/part4/paper_ready_results.csv \
  results/part4/CLAIMS.md \
  rtl/embodicore_semantic_controller.sv \
  rtl/embodicore_condition_ingress.sv
do
  [ -f "$ROOT/$f" ] && pass "$f" || pending "$f"
done

# Hygiene
FORBIDDEN="$(
  find "$ROOT" \
    \( -name '.venv*' -o -name 'venv' -o -name '__pycache__' \
    -o -name '*.pyc' -o -name '.git' -o -name 'third_party' \
    -o -name '*.ckpt' -o -name '*.pth' -o -name '*.pt' \
    -o -name '*.safetensors' -o -name '*.npz' -o -name '*.npy' \) \
    -print 2>/dev/null || true
)"
[ -z "$FORBIDDEN" ] && pass "open-source hygiene" || {
  fail "forbidden artifacts found"
  printf '%s\n' "$FORBIDDEN"
}

BIG50="$(find "$ROOT" -type f -size +50M -print 2>/dev/null || true)"
[ -z "$BIG50" ] && pass "no files >50 MiB" || {
  fail "files >50 MiB found"
  printf '%s\n' "$BIG50"
}

SECRET_HITS="$(
  grep -RInE \
    --exclude='verify_release.sh' \
    --exclude='MANIFEST.sha256' \
    '(-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----|github_pat_[A-Za-z0-9_]{20,}|ghp_[A-Za-z0-9]{30,}|AKIA[0-9A-Z]{16}|sk-[A-Za-z0-9]{32,})' \
    "$ROOT" 2>/dev/null || true
)"
[ -z "$SECRET_HITS" ] && pass "high-confidence secret scan" || {
  fail "possible secret material found"
  printf '%s\n' "$SECRET_HITS"
}

echo
echo "Failures: $FAIL"
echo "Pending optional artifacts: $PENDING"
echo

if [ "$FAIL" -eq 0 ]; then
  echo "AIRSEAI EmbodiCore core release verification: PASS"
  if [ "$PENDING" -gt 0 ]; then
    echo "Optional research evidence remains PENDING; see ARTIFACT_STATUS.md."
  fi
  exit 0
else
  echo "AIRSEAI EmbodiCore core release verification: FAIL"
  exit 1
fi
