# EmbodiCore

**Semantics-Aware Hardware Compilation for Stateful Embodied AI**

EmbodiCore studies a hardware-compilation boundary that is easy to miss in
stateful embodied AI: a value can remain physically resident after it has
stopped being semantically valid. The compiler therefore treats execution
lifetime, reset, update, and reuse rules as **legality constraints before
hardware optimization**.

> **Execution semantics determine what is behaviorally legal; hardware
> constraints determine what is physically feasible and preferable within the
> legal set.**

This directory is the public AIRSEAI research artifact associated with the
EmbodiCore CAL manuscript.

## 1. What this artifact contains

The release is deliberately layered:

- `semantics/` — execution-contract construction and semantic negative controls.
- `tracing/` — real-policy trace collection / preflight utilities retained from
  the Mamba Policy experiment.
- `compiler/` — retained Part-III source when it is discoverable locally, plus
  a small reference semantic-filter implementation. The reference file
  illustrates the legality interface; it is not presented as a reconstruction
  of a missing historical cost model.
- `fidelity/` — retained numerical-fidelity source when discoverable, plus
  verification notes for the frozen action-level record.
- `results/frozen/` — machine-readable frozen claim records for Part III /
  Part III.5 and a claim-to-evidence index.
- `results/part4/` — the immutable pre-handoff Part-IV Mac evidence, including
  `PART4_MAC_FINAL.json` and the RTL semantic/memory experiment records.
- `rtl/` — the exact portable SystemVerilog semantic controller and condition
  ingress RTL carried into the PG2K400 handoff, plus the board self-test top
  and testbench.
- `hardware/pg2k400/pre_handoff/` — the manifest-verified FPGA handoff package.
- `hardware/pg2k400/evidence/` — post-handoff physical resource and timing
  evidence, including the vendor screenshots and a machine-readable result
  record.
- `release_assets/` — hashes for large/restricted inputs that are intentionally
  not redistributed.

The artifact separates **source**, **raw archival evidence**, **frozen result
records**, and **post-handoff physical evidence** instead of treating them as
interchangeable.

## 2. Frozen headline results

The release verifier checks the following paper-visible results.

### Semantic legality and DSE

- 4,096 structural candidates were considered.
- 3,664 satisfy the primary resource proxy; 687 are both feasible and
  semantically legal. Thus semantic legality removes 81.25% of the
  resource-feasible space.
- Candidate 759 is the frozen best legal point; candidate 4087 is the matched
  contract-agnostic negative control.
- The contract-agnostic top 20 are illegal under all three objective regimes.
- Stale observation-condition reuse gives mean executed-action L2 of 0.329 over
  96 within-episode updates and 10.61 over four sampled reset boundaries.

### Numerical fidelity

P1 uses FP16 weights/activations with FP32 scan state and accumulation. Over
900 policy invocations, its executed-action L2 has mean `4.11e-4`, p99
`8.86e-4`, and maximum `1.29e-3`; 900/900 invocations satisfy the frozen
`epsilon_a = 0.10` contract.

For this artifact, **executed-action L2** means a per-policy-invocation L2 norm
over the recorded executed-action tensor. The retained trace schema is three
executed actions by 24 action dimensions (`3 x 24`) per invocation.

### Portable RTL

Across the frozen 900-policy geometry (10 denoising calls per policy):

- required scan resets: `9,000 / 9,000`;
- condition loads: `9,000 -> 900`;
- trace-visible condition ingress: `4,608,000 B -> 460,800 B`;
- reduction: `90%`, or `10x` condition-ingress ratio;
- illegal no-reset stress: 8,990 stale-condition uses and 8,999 illegal scan
  carries;
- generic controller cost relative to Matched-NoReuse: `+1 LUT / +0 FF`.

The 10x result is a **local condition-ingress reduction**, not a 10x whole-policy speedup. The measured representative-kernel serialized-cycle
effect is only about `0.001375%–0.012095%`.

### PG2K400 physical anchor

The post-handoff vendor evidence records:

- self-test top: `294 LUT / 252 FF`;
- condition ingress: `173 LUT / 162 FF`;
- semantic controller: `2 LUT / 2 FF`;
- displayed Distributed RAM / APM / DRM: zero for those rows;
- requested clock: `50.0000 MHz`;
- reported Fmax: `307.4085 MHz`;
- reported slack: `+16.747 ns`.

This establishes **physical realizability of the semantic-control / ingress
anchor only**. It is not evidence for a full 12-mixer Mamba accelerator,
end-to-end FPGA policy speedup, board-level action correctness, or
cross-device portability.

## 3. One-command verification

From this directory:

```bash
bash scripts/verify_release.sh
```

A successful claim-audit release ends with:

```text
EMBODICORE CAL CLAIM-AUDIT ARTIFACT: PASS
```

The verifier checks the immutable Part-IV record, Part-III frozen result
record, RTL hashes and semantic counts, FPGA handoff manifest, post-handoff
resource/timing evidence, claim boundaries, and the release manifest.

## 4. Reproducibility levels

**Level A — self-contained claim audit.** Requires only Python 3 and standard
Unix tools. This is the guaranteed path shipped here.

**Level B — semantic/source rerun.** The Part-I semantic code and Part-II trace
utilities are retained from the research workspace. Their heavier real-policy
paths require the upstream Mamba Policy environment and checkpoint.

**Level C — raw Part-III rerun.** If the original Part-III source and raw DSE /
fidelity files are found on the local machine, the V7 builder copies them into
`compiler/original/`, `fidelity/original/`, and `results/raw_part3/`. If those
historical files are not available, the release says so explicitly and ships a
frozen result record; it does **not** manufacture a 4,096-row candidate table
or pretend a derived table is raw data.

**Level D — FPGA regeneration.** The exact pre-handoff RTL/self-test package is
retained under `hardware/pg2k400/pre_handoff/`. Regenerating physical reports
requires the corresponding vendor PDS toolchain and board.

## 5. Why there are two PG2K400 records

`results/part4/PART4_MAC_FINAL.json` was frozen **before** the board handoff and
therefore correctly says `PG2K400_anchor_complete=false`. That historical file
is never edited.

The later board run is recorded separately in
`hardware/pg2k400/evidence/PG2K400_PHYSICAL_RESULTS.json` and the two included
vendor screenshots. Keeping the records separate preserves chronology and
prevents a post-hoc edit of the Mac freeze.

## 6. Evidence map

See `ARTIFACT.md` for a claim-by-claim map. The short version is:

| Claim layer | Primary shipped evidence |
|---|---|
| lifetime semantics | `results/semantics/` + Part-III frozen record |
| DSE legality | `results/frozen/PART3_FROZEN_SUMMARY.json` + raw archive if discovered |
| action fidelity | Part-III frozen record + raw fidelity archive if discovered |
| RTL reset/reuse | `results/part4/` + exact RTL |
| generic logic cost | immutable Part-IV frozen record |
| PG2K400 physical anchor | post-handoff JSON + vendor screenshots |

## 7. Claim boundaries

The release intentionally blocks these interpretations:

- 90% whole-accelerator latency reduction;
- 10x whole-policy speedup;
- measured full-12-mixer FPGA speedup;
- full accelerator area inferred from the tiny semantic controller;
- board LED/self-test status used as policy-action correctness;
- PG2K400 used to claim cross-device performance portability;
- no-reset stress counts described as empirical episode-boundary statistics.

These boundaries are part of the artifact, not footnotes to it.

## 8. External data and provenance

Large checkpoints, raw traces, extracted weights, Python environments, and
vendored third-party repositories are not committed into the public AIRSEAI
subtree. When they are present locally, V7 records their SHA-256 hashes in
`release_assets/OMITTED_DATA_SHA256.txt`.

`THIRD_PARTY.md` records the upstream Mamba Policy / Mamba provenance that can
be recovered from the local workspace. `PROVENANCE.json` records which
evidence was found locally and which was supplied by the frozen support
bundle.

## 9. Extending EmbodiCore

A new policy backend should supply:

1. nested execution domains;
2. machine-readable lifetime/reset/update/reuse contracts;
3. source- or dependency-derived evidence for inferred boundaries;
4. explicit annotations where physical-loop meaning cannot be inferred;
5. a legality filter that runs before deployment ranking;
6. action-boundary numerical acceptance tests;
7. backend-specific lowering and verification evidence.

A new hardware target changes physical feasibility and ranking; it should not
silently change semantic validity.

## 10. Scope

This artifact demonstrates one stateful policy family. Dynamic real-weight
microtraces were retained for representative mixers 0, 6, and 11, although the
static real-weight census covers all 12 mixers. The portable hardware path
covers lifetime/reset/cache-control and condition ingress rather than a full
robot SoC or 12-mixer arithmetic datapath.

Those limitations are intentional and are part of the reproducibility
contract.

## Citation and license

See `CITATION.cff`. Licensing follows the parent AIRSEAI repository unless a
subtree notice states otherwise.
