#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import csv, hashlib, json, math, sys

ROOT = Path(__file__).resolve().parents[1]
ERR = []
WARN = []

def req(cond, msg):
    if not cond:
        ERR.append(msg)

def approx(a,b,tol=1e-12):
    return abs(float(a)-float(b)) <= tol

def loadj(rel):
    p=ROOT/rel
    req(p.is_file(), f"missing {rel}")
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception as e:
        ERR.append(f"cannot parse {rel}: {e}")
        return {}

def sha256(p):
    h=hashlib.sha256()
    with open(p,"rb") as f:
        for b in iter(lambda:f.read(1<<20), b""):
            h.update(b)
    return h.hexdigest()

# Required documentation / evidence skeleton
for rel in [
    "README.md","ARTIFACT.md","REPRODUCIBILITY.md","THIRD_PARTY.md",
    "PROVENANCE.json","EVIDENCE_STATUS.md","RELEASE_POLICY.md",
    "compiler/README.md","results/frozen/README.md","results/raw_part3/README.md",
    "results/frozen/PART3_FROZEN_SUMMARY.json",
    "results/frozen/PAPER_CLAIM_INDEX.csv",
    "results/part4/PART4_MAC_FINAL.json",
    "results/part4/EXPERIMENT3_RTL_SEMANTICS.json",
    "results/part4/EXPERIMENT4_RTL_MEMORY.json",
    "rtl/embodicore_semantic_controller.sv",
    "rtl/embodicore_condition_ingress.sv",
    "rtl/embodicore_pg_selftest_top.sv",
    "rtl/testbench/tb_pg_selftest.sv",
    "hardware/pg2k400/evidence/PG2K400_PHYSICAL_RESULTS.json",
    "hardware/pg2k400/evidence/pg2k400_resource_utilization.png",
    "hardware/pg2k400/evidence/pg2k400_timing_summary.png",
]:
    req((ROOT/rel).is_file() and (ROOT/rel).stat().st_size>0, f"missing/empty {rel}")

# Part III frozen record
p3=loadj("results/frozen/PART3_FROZEN_SUMMARY.json")
dse=p3.get("structural_dse",{})
req(dse.get("all_candidates")==4096, "Part III all_candidates != 4096")
req(dse.get("resource_feasible_primary_budget_0_80")==3664, "Part III resource_feasible != 3664")
req(dse.get("legal_and_resource_feasible")==687, "Part III legal+feasible != 687")
req(approx(dse.get("semantic_elimination_fraction_of_resource_feasible",0),0.8125), "Part III semantic elimination != 81.25%")
req(dse.get("best_legal_candidate")==759, "best legal candidate != 759")
req(dse.get("balanced_agnostic_winner")==4087, "agnostic winner != 4087")
req(dse.get("agnostic_top20_illegal_each_objective") is True, "agnostic top-20 guardrail missing")
f=p3.get("fidelity",{})
req(f.get("representative_real_weight_mixer_calls")==1920, "mixer calls != 1920")
req(f.get("policy_invocations")==900, "policy invocations != 900")
req(f.get("passes")==900, "P1 passes != 900")
req(approx(f.get("P1_action_p99_L2",0),8.86e-4,1e-12), "P1 action p99 mismatch")
req(approx(f.get("P1_action_max_L2",0),1.29e-3,1e-12), "P1 action max mismatch")
req(approx(f.get("epsilon_a",0),0.10,1e-12), "epsilon_a mismatch")
neg=p3.get("semantic_negative_controls",{})
req(approx(neg.get("stale_condition_within_episode_mean_action_L2",0),0.329), "stale within-episode L2 mismatch")
req(approx(neg.get("stale_condition_reset_mean_action_L2",0),10.61), "stale reset L2 mismatch")

# Immutable Part IV Mac freeze
p4=loadj("results/part4/PART4_MAC_FINAL.json")
req(p4.get("status")=="PASS", "PART4_MAC_FINAL status != PASS")
h=p4.get("headline",{})
for k,v in {
    "condition_traffic_reduction_percent":90.0,
    "condition_traffic_ratio":10.0,
    "embodicore_scan_resets":9000,
    "agnostic_stale_condition_uses":8990,
    "agnostic_illegal_scan_carries":8999,
    "generic_semantic_controller_LUT_overhead":1,
    "generic_semantic_controller_FF_overhead":0,
}.items():
    req(k in h and approx(h[k],v), f"Part IV headline mismatch: {k}")
rng=h.get("representative_cycle_reduction_range_percent",[])
req(isinstance(rng,list) and len(rng)==2, "missing representative cycle range")
if isinstance(rng,list) and len(rng)==2:
    req(approx(rng[0],0.001374612435656175,1e-15), "cycle range low mismatch")
    req(approx(rng[1],0.01209514850154525,1e-15), "cycle range high mismatch")
req(p4.get("coverage",{}).get("full_12_mixer_cycle_claim") is False,
    "full 12-mixer cycle claim must remain blocked")
# Historical chronology must remain intact.
req(p4.get("coverage",{}).get("PG2K400_anchor_complete") is False,
    "historical pre-handoff PG2K400 flag was altered")

e3=loadj("results/part4/EXPERIMENT3_RTL_SEMANTICS.json")
req(e3.get("status")=="PASS","Experiment 3 status != PASS")
o=e3.get("observed",{})
for k,v in {
    "matched_cond_loads":9000,"embodicore_cond_loads":900,"agnostic_cond_loads":1,
    "matched_scan_resets":9000,"embodicore_scan_resets":9000,"agnostic_scan_resets":1,
    "agnostic_stale_condition_uses":8990,"agnostic_illegal_scan_carries":8999
}.items():
    req(o.get(k)==v, f"Experiment 3 mismatch: {k}")
ct=e3.get("condition_traffic",{})
req(ct.get("Matched-NoReuse_bytes")==4608000, "matched ingress bytes mismatch")
req(ct.get("EmbodiCore-759_bytes")==460800, "EmbodiCore ingress bytes mismatch")
req(approx(ct.get("ratio",0),10.0), "ingress ratio mismatch")

e4=loadj("results/part4/EXPERIMENT4_RTL_MEMORY.json")
req(e4.get("status")=="PASS","Experiment 4 status != PASS")
for bw in ["64","128","256","512"]:
    c=e4.get("comparisons",{}).get(bw,{})
    req(approx(c.get("legal_traffic_reduction_percent",0),90.0), f"{bw}-bit traffic mismatch")
    req(approx(c.get("matched_over_embodicore_cycle_ratio",0),10.0), f"{bw}-bit ratio mismatch")
    req(c.get("agnostic_is_semantically_legal") is False, f"{bw}-bit agnostic legality mismatch")

# Exact RTL hashes carried by the immutable Part-IV evidence
rtl_expect={
 "rtl/embodicore_semantic_controller.sv":"0a7a4e1b86dde4a7da39619fa7d77d9459a9e8fc910ea17afe1b02a12eb7d05d",
 "rtl/embodicore_condition_ingress.sv":"3162e92e6c9aa20a44be950c9f8358211b20c30c7e9e5428b09360c0a7588bc3",
}
for rel, expected in rtl_expect.items():
    p=ROOT/rel
    if p.is_file():
        req(sha256(p)==expected, f"RTL hash mismatch: {rel}")

# PG2K400 post-handoff evidence
pg=loadj("hardware/pg2k400/evidence/PG2K400_PHYSICAL_RESULTS.json")
ru=pg.get("resource_utilization",{})
req(ru.get("embodicore_pg_selftest_top",{}).get("LUT")==294, "PG self-test LUT != 294")
req(ru.get("embodicore_pg_selftest_top",{}).get("FF")==252, "PG self-test FF != 252")
req(ru.get("embodicore_condition_ingress",{}).get("LUT")==173, "PG ingress LUT != 173")
req(ru.get("embodicore_condition_ingress",{}).get("FF")==162, "PG ingress FF != 162")
req(ru.get("embodicore_semantic_controller",{}).get("LUT")==2, "PG semantic ctrl LUT != 2")
req(ru.get("embodicore_semantic_controller",{}).get("FF")==2, "PG semantic ctrl FF != 2")
tm=pg.get("timing",{})
req(approx(tm.get("requested_frequency_MHz",0),50.0), "PG requested frequency mismatch")
req(approx(tm.get("Fmax_MHz",0),307.4085,1e-10), "PG Fmax mismatch")
req(approx(tm.get("slack_ns",0),16.747,1e-10), "PG slack mismatch")
for key, rel in [
    ("resource_screenshot","hardware/pg2k400/evidence/pg2k400_resource_utilization.png"),
    ("timing_screenshot","hardware/pg2k400/evidence/pg2k400_timing_summary.png")
]:
    if (ROOT/rel).is_file():
        req(sha256(ROOT/rel)==pg.get("evidence",{}).get(key,{}).get("sha256"),
            f"PG screenshot hash mismatch: {rel}")

# Provenance / artifact-classification guardrails
prov=loadj("PROVENANCE.json")
eq=prov.get("evidence_sources",{})
req(eq.get("part3_original_source_recovered") is False,
    "Part-III source provenance must remain NOT RECOVERED for this release")
req(eq.get("part3_original_results_recovered") is False,
    "Part-III raw-result provenance must remain NOT RECOVERED for this release")
req(prov.get("artifact_classification")=="claim-audit artifact plus reference implementation",
    "missing/incorrect artifact classification")

req("derived" in str(p3.get("provenance_status","")).lower(),
    "Part-III frozen summary must identify derived/frozen provenance")

raw_dir=ROOT/"results/raw_part3"
raw_payload=[]
if raw_dir.exists():
    for q in raw_dir.rglob("*"):
        if q.is_file() and q.name.lower() not in {"readme.md","not_recovered.md"}:
            raw_payload.append(q)
req(not raw_payload,
    "PROVENANCE says Part-III raw archive is not recovered, but raw payload files are present")

raw_note=(ROOT/"results/raw_part3/README.md").read_text(errors="ignore") if (ROOT/"results/raw_part3/README.md").is_file() else ""
req("NOT RECOVERED" in raw_note,
    "raw Part-III status README must explicitly say NOT RECOVERED")

# Claim-boundary prose must remain explicit in README.
readme=(ROOT/"README.md").read_text(errors="ignore")
readme_norm=" ".join(readme.split())
for phrase in [
    "claim-audit artifact plus reference implementation",
    "not a 10x whole-policy speedup",
    "physical realizability",
    "not evidence for a full 12-mixer Mamba accelerator",
    "does not manufacture a 4,096-row candidate table",
    "Not independently rerunnable",
]:
    req(phrase in readme_norm, f"README missing claim boundary: {phrase}")

# Report original Part-III archival status from provenance.
if eq.get("part3_original_source_recovered") or eq.get("part3_original_results_recovered"):
    raw_status="RECOVERED (provenance says original Part-III material is present)"
else:
    raw_status="NOT RECOVERED; frozen claim record shipped and gap disclosed"

if ERR:
    print("EmbodiCore CAL claim-audit verification: FAIL")
    for e in ERR:
        print("  FAIL:",e)
    sys.exit(1)

print("EmbodiCore CAL claim-audit verification: PASS")
print("  Part III frozen DSE/fidelity record: PASS")
print("  Part IV immutable Mac freeze: PASS")
print("  RTL semantic/reset/ingress evidence: PASS")
print("  PG2K400 post-handoff physical evidence: PASS")
print("  Unsupported-claim guardrails: PASS")
print("  Original Part-III raw archive:",raw_status)
