from pathlib import Path
import json
import re
import subprocess
from datetime import datetime

ROOT = Path.cwd()
MP = ROOT / "third_party" / "Mamba-Policy"
MAMBA = ROOT / "third_party" / "mamba"
OUT = ROOT / "part1_semantics"
OUT.mkdir(parents=True, exist_ok=True)

if not (MP / ".git").exists():
    raise SystemExit(f"ERROR: missing repo: {MP}")
if not (MAMBA / ".git").exists():
    raise SystemExit(f"ERROR: missing repo: {MAMBA}")

dp3 = MP / "3D-Diffusion-Policy" / "diffusion_policy_3d" / "policy" / "dp3.py"
unet = MP / "3D-Diffusion-Policy" / "diffusion_policy_3d" / "model" / "diffusion" / "conditional_unet1d.py"
cfg = MP / "3D-Diffusion-Policy" / "diffusion_policy_3d" / "config" / "dp3_mamba.yaml"
mamba_simple = MAMBA / "mamba_ssm" / "modules" / "mamba_simple.py"

for p in [dp3, unet, cfg, mamba_simple]:
    if not p.exists():
        raise SystemExit(f"ERROR: expected source file not found: {p}")

def git_head(repo):
    return subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()

def numbered_context(text, pattern, before=6, after=10):
    lines = text.splitlines()
    rx = re.compile(pattern)
    hits = []
    for i, line in enumerate(lines):
        if rx.search(line):
            lo = max(0, i-before)
            hi = min(len(lines), i+after+1)
            hits.append("\n".join(f"{j+1:5d}: {lines[j]}" for j in range(lo, hi)))
    return "\n\n".join(hits)

dp3_t = dp3.read_text(errors="ignore")
unet_t = unet.read_text(errors="ignore")
cfg_t = cfg.read_text(errors="ignore")
mamba_t = mamba_simple.read_text(errors="ignore")

checks = {
    "ddim_loop_exists": bool(re.search(r"for\s+t\s+in\s+.*scheduler\.timesteps", dp3_t)),
    "global_cond_passed_to_model": "global_cond=global_cond" in dp3_t,
    "trajectory_updated_by_scheduler": "scheduler.step" in dp3_t and "trajectory" in dp3_t,
    "global_cond_formed_from_observation": "global_cond" in dp3_t and "obs_feature" in dp3_t,
    "mamba_mixer_called_without_explicit_inference_params": bool(
        re.search(r"self\.mixer\s*\(\s*self\.norm1\(x\)\s*\)", unet_t)
    ),
    "official_mamba_checks_inference_params": "if inference_params is not None" in mamba_t,
    "film_config_present": bool(re.search(r"condition_type:\s*film", cfg_t)),
    "condition_concat_present": bool(re.search(r"global_feature\s*=\s*torch\.cat", unet_t)),
}
overall = all(checks.values())

report = [
    "=== EmbodiCore Part I Source Audit ===",
    f"Timestamp: {datetime.now().isoformat()}",
    f"Mamba-Policy commit: {git_head(MP)}",
    f"state-spaces/mamba commit: {git_head(MAMBA)}",
    "",
    "=== Boolean source checks ===",
]
for k, v in checks.items():
    report.append(f"{k}: {v}")
report += [
    f"SOURCE_AUDIT_PASS: {overall}",
    "",
    "=== A. DDIM loop ===",
    numbered_context(dp3_t, r"for\s+t\s+in\s+.*scheduler\.timesteps", 8, 18),
    "",
    "=== B. global_cond construction/use ===",
    numbered_context(dp3_t, r"global_cond", 5, 8),
    "",
    "=== C. MambaVisionBlock mixer call ===",
    numbered_context(unet_t, r"self\.mixer\s*\(", 8, 10),
    "",
    "=== D. Official Mamba inference_params/cache path ===",
    numbered_context(mamba_t, r"if inference_params is not None", 8, 22),
    "",
    "=== E. Condition construction ===",
    numbered_context(unet_t, r"global_feature\s*=\s*torch\.cat", 8, 15),
    "",
    "=== F. FiLM configuration ===",
    numbered_context(cfg_t, r"condition_type:\s*film", 4, 4),
    "",
    "=== Interpretation frozen for Part I ===",
    "1) global_cond is policy-local while observation is fixed.",
    "2) trajectory and timestep evolve across DDIM iterations.",
    "3) selective-scan state is scan-local in this policy context.",
    "4) cross-call reuse must respect reset and dependency semantics.",
]

(OUT / "source_audit.txt").write_text("\n".join(report))
(OUT / "source_audit_checks.json").write_text(json.dumps({
    "checks": checks,
    "source_audit_pass": overall,
    "mamba_policy_commit": git_head(MP),
    "state_spaces_mamba_commit": git_head(MAMBA),
}, indent=2))

print(json.dumps(checks, indent=2))
print(f"SOURCE_AUDIT_PASS={overall}")
if not overall:
    raise SystemExit(3)
