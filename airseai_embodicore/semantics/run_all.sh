#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

if [[ "$(uname -m)" != "arm64" ]]; then
  echo "ERROR: uname -m is not arm64. Do not run Part I under Rosetta." >&2
  exit 2
fi

if [[ ! -d ".venv-part1" ]]; then
  echo "ERROR: ${ROOT}/.venv-part1 does not exist." >&2
  exit 2
fi

source .venv-part1/bin/activate

mkdir -p part1_semantics
cp part1/mamba_v1_ref.py part1_semantics/
cp part1/run_semantic_tests.py part1_semantics/
cp part1/build_contract.py part1_semantics/
cp part1/source_audit.py part1_semantics/

python part1/source_audit.py | tee part1_semantics/source_audit_stdout.txt
python part1/build_contract.py | tee part1_semantics/contract_stdout.txt
python part1/run_semantic_tests.py | tee part1_semantics/test_stdout.txt

python - <<'PY'
from pathlib import Path
import json, platform, sys, torch

out = Path("part1_semantics")
audit = json.loads((out / "source_audit_checks.json").read_text())
metrics = json.loads((out / "semantic_test_metrics.json").read_text())
contract = json.loads((out / "lifetime_contract.json").read_text())

env = {
    "machine": platform.machine(),
    "platform": platform.platform(),
    "python": platform.python_version(),
    "torch": torch.__version__,
    "mps_built": metrics["mps_built"],
    "mps_available": metrics["mps_available"],
}
(out / "environment.json").write_text(json.dumps(env, indent=2))

source_pass = bool(audit["source_audit_pass"])
semantic_pass = bool(metrics["semantic_tests_pass"])
mps_pass = bool(metrics["mps_consistency_pass"])
arm_pass = platform.machine() == "arm64"
overall = source_pass and semantic_pass and mps_pass and arm_pass

auto_like = sum(
    1 for x in contract["objects"]
    if x["inference"] in {
        "source_dataflow",
        "source_loop_variable",
        "dependency_analysis",
        "source_loop_invariance",
        "compiler_candidate_from_algebra_plus_dependency_analysis"
    }
)
explicit_like = len(contract["objects"]) - auto_like

summary = f"""EmbodiCore Part I Summary — v11
==================================

Machine architecture: {platform.machine()}
Python: {platform.python_version()}
PyTorch: {torch.__version__}
MPS available: {metrics['mps_available']}

SOURCE AUDIT
------------
Source audit PASS: {source_pass}
Mamba-Policy commit: {audit['mamba_policy_commit']}
state-spaces/mamba commit: {audit['state_spaces_mamba_commit']}

REFERENCE CONSISTENCY
---------------------
CPU/MPS reference max abs error: {metrics['cpu_mps_reference_max_abs_error']}
CPU/MPS reference mean abs error: {metrics['cpu_mps_reference_mean_abs_error']}
MPS consistency PASS: {mps_pass}

LEGAL REUSE
-----------
Policy-local condition reuse CPU max abs error: {metrics['legal_policy_local_reuse_cpu_max_abs_error']}
Policy-local condition reuse CPU mean abs error: {metrics['legal_policy_local_reuse_cpu_mean_abs_error']}
Legal reuse PASS: {metrics['legal_reuse_pass']}

ILLEGAL CROSS-DOMAIN STATE CARRY
--------------------------------
Output max abs error: {metrics['illegal_scan_state_carry_output_max_abs_error']}
Output mean abs error: {metrics['illegal_scan_state_carry_output_mean_abs_error']}
State max abs error: {metrics['illegal_scan_state_carry_state_max_abs_error']}
State mean abs error: {metrics['illegal_scan_state_carry_state_mean_abs_error']}
Illegal scan-state carry negative-control PASS: {metrics['illegal_scan_state_carry_pass']}

RESET-BOUNDARY NEGATIVE CONTROL
-------------------------------
Stale condition after new observation max abs error: {metrics['stale_condition_after_new_observation_cpu_max_abs_error']}
Stale condition after new observation mean abs error: {metrics['stale_condition_after_new_observation_cpu_mean_abs_error']}
New-observation reset negative-control PASS: {metrics['stale_condition_reset_pass']}

EXECUTION CONTRACT
------------------
Schema: <lifetime, reset_event, update_event, legal_reuse_scope>
Contract objects: {len(contract['objects'])}
Source/dependency inferable or compiler-candidate objects: {auto_like}
Objects requiring explicit policy-boundary semantic assertion: {explicit_like}

PART I CLAIM SUPPORTED
----------------------
Part I supports only the source-level/numerical claim that policy execution
context constrains legal state persistence and cross-call reuse.
It does NOT yet establish real-checkpoint action error, FPGA benefit,
contract-agnostic DSE ranking, or closed-loop success.

OVERALL PART I: {'PASS' if overall else 'FAIL'}
"""
(out / "summary.txt").write_text(summary)
print("\n" + summary)

if not overall:
    sys.exit(4)
PY

rm -f part1_semantics.zip
zip -qr part1_semantics.zip part1_semantics

echo
echo "============================================================"
echo "DONE — PART I PASS"
echo "Upload this file to ChatGPT:"
echo "${ROOT}/part1_semantics.zip"
echo "============================================================"
