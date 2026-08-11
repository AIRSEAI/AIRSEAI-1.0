# EmbodiCore

**Semantics-Aware Hardware Compilation for Stateful Embodied AI**

EmbodiCore is a **claim-audit artifact plus reference implementation** for the
CAL manuscript. Its central rule is that execution lifetime, reset, update,
and reuse semantics constrain legality **before** hardware optimization.

> **Execution semantics determine what is behaviorally legal; hardware
> constraints determine what is physically feasible and preferable within the
> legal set.**

## Artifact classification

This public release guarantees a self-contained audit of the manuscript's
shipped semantic, frozen-result, RTL, and PG2K400 claims. It also includes
runnable semantic/source utilities and exact portable RTL.

It does **not** currently provide an independent rerun of the historical
4,096-candidate Part-III DSE or the 900-invocation action replay from raw data,
because the original Part-III source/results and large replay arrays were not
recovered into the public archive. Those results are therefore labeled
**frozen claim records**, not raw reproducibility evidence.

That distinction is intentional and machine-checked.

## 1. What is shipped

- `semantics/` — execution-contract construction and semantic negative controls.
- `tracing/` — real-policy trace collection/preflight utilities retained from
  the Mamba Policy experiment.
- `compiler/` — a compact reference semantic-legality filter; see its README
  for the boundary between the reference layer and the unavailable historical
  Part-III DSE cost model.
- `results/semantics/` — source-level semantic measurements.
- `results/frozen/` — machine-readable frozen Part-III/III.5 result record and
  claim index. These are derived/frozen records, not a reconstructed raw DSE.
- `results/raw_part3/README.md` — explicit archival status of the unrecovered
  original Part-III files.
- `results/part4/` — immutable pre-handoff Part-IV Mac evidence.
- `rtl/` — exact portable SystemVerilog semantic controller, condition-ingress
  RTL, PG self-test top, and testbench.
- `hardware/pg2k400/pre_handoff/` — manifest-verified FPGA handoff package.
- `hardware/pg2k400/evidence/` — post-handoff PG2K400 resource/timing evidence.
- `scripts/verify_release.sh` — one-command claim-audit verifier.

## 2. Fresh-clone verification

From a clean checkout of the AIRSEAI repository:

```bash
cd airseai_embodicore
bash scripts/verify_release.sh
```

A successful run ends with:

```text
EMBODICORE CAL CLAIM-AUDIT ARTIFACT: PASS
```

The verifier checks the frozen Part-III record, immutable Part-IV evidence,
RTL hashes and semantic counts, PG2K400 handoff manifest, post-handoff physical
evidence, claim-boundary wording, provenance status, and the release manifest.

If Icarus Verilog is installed, it also compiles/runs the included PG self-test.
The repository CI installs Icarus Verilog and runs this verifier on a fresh
GitHub Actions checkout.

## 3. What is independently rerunnable from this checkout?

| Layer | Fresh-checkout status | Meaning |
|---|---|---|
| Minimal semantic-legality example | **Rerunnable** | Demonstrates legality-before-ranking |
| Part-I semantic/source checks | **Rerunnable with listed dependencies** | Supports source-level semantic necessity |
| Part-II trace utilities | **Source shipped** | Full replay needs upstream checkpoint/data |
| Historical 4,096-candidate Part-III DSE | **Not independently rerunnable** | Original generator/cost model/raw table not recovered |
| Historical Part-III action replay | **Not independently rerunnable** | Frozen record shipped; raw replay arrays omitted/unrecovered |
| Part-IV structured evidence audit | **Rerunnable audit** | Immutable JSON/RTL records checked |
| PG self-test RTL | **Rerunnable with Icarus** | Portable RTL compile/simulation |
| PG2K400 place-and-route | **Evidence shipped; vendor rerun requires PDS** | Physical anchor only |

## 4. Frozen headline claims

### Semantic legality / DSE record

- 4,096 structural candidates.
- 3,664 resource-feasible at the primary 0.80 budget.
- 687 legal + feasible; semantic legality removes 81.25% of the
  resource-feasible candidates.
- Frozen best legal point: candidate 759.
- Matched contract-agnostic negative control: candidate 4087.
- Contract-agnostic top-20 are illegal under all three frozen objectives.
- Stale-condition mean executed-action L2: 0.329 over 96 within-episode updates
  and 10.61 over four sampled reset-boundary comparisons.

These are frozen Part-III claim records. The release does not manufacture a
4,096-row candidate table to make them appear independently reproducible.

### Numerical-fidelity record

P1 uses FP16 weights/activations with FP32 scan state and accumulation. Over
900 policy invocations, the frozen executed-action L2 record has mean
`4.11e-4`, p99 `8.86e-4`, maximum `1.29e-3`, and 900/900 passes under
`epsilon_a = 0.10`.

The retained trace schema records three executed actions by 24 action
dimensions (`3 x 24`) per invocation.

### Portable RTL

Across the frozen 900-policy geometry with 10 denoising calls per policy:

- required scan resets: `9,000 / 9,000`;
- condition loads: `9,000 -> 900`;
- condition ingress: `4,608,000 B -> 460,800 B`;
- ingress reduction: `90%`, or `10x` ratio;
- illegal no-reset stress: 8,990 stale-condition uses and 8,999 illegal scan
  carries;
- generic semantic-controller delta: `+1 LUT / +0 FF`.

The 10x result is a **local condition-ingress reduction**, not a 10x
whole-policy speedup. The representative serialized-cycle effect is only
approximately `0.001375%–0.012095%`.

### PG2K400 physical anchor

The returned vendor evidence records:

- self-test top: `294 LUT / 252 FF`;
- condition ingress: `173 LUT / 162 FF`;
- semantic controller: `2 LUT / 2 FF`;
- requested clock: `50.0000 MHz`;
- Fmax: `307.4085 MHz`;
- slack: `+16.747 ns`.

This establishes **physical realizability** of the semantic-control/condition-
ingress anchor. It is not evidence for a full 12-mixer Mamba accelerator,
end-to-end FPGA policy speedup, board-level policy-action correctness, or
cross-device performance portability.

## 5. Why the agnostic DSE options are meaningful

The agnostic lifetime options model residency/hoisting choices that are legal
under tensor dependency and storage-liveness analysis alone. They become
illegal only after external observation/reset events—events absent from the
captured neural graph—are introduced by the execution contract. The reference
semantic filter demonstrates this distinction; it does not recreate the
missing historical Part-III cost model.

## 6. Evidence chronology

`results/part4/PART4_MAC_FINAL.json` was frozen **before** board handoff and
therefore correctly retains `PG2K400_anchor_complete=false`. V8 does not edit
that historical record. The completed board run is represented separately in
`hardware/pg2k400/evidence/`.

## 7. Claim boundaries

The artifact explicitly blocks these interpretations:

- 90% whole-accelerator latency reduction;
- 10x whole-policy speedup;
- measured full-12-mixer FPGA speedup;
- full accelerator area inferred from the semantic controller;
- board LED/self-test status used as policy-action correctness;
- PG2K400 used to claim cross-device performance portability;
- the frozen Part-III summary described as raw DSE evidence.

## 8. Release pinning

For publication, cite an **immutable tag or exact merge commit**, not the moving
`main` branch. See `RELEASE_POLICY.md`.

## 9. Citation and license

See `CITATION.cff`. Licensing follows the parent AIRSEAI repository unless a
subtree notice states otherwise.
