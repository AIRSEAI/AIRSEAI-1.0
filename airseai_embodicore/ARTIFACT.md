# EmbodiCore Artifact Evidence Map

This map distinguishes independently rerunnable material, original frozen
structured evidence, derived/frozen claim records, and post-handoff physical
evidence.

| Manuscript claim | Primary shipped evidence | Public status |
|---|---|---|
| execution lifetime affects correctness | `semantics/`, `results/semantics/` | source/rerunnable |
| 4,096 / 3,664 / 687 DSE | `results/frozen/PART3_FROZEN_SUMMARY.json` | **frozen claim record; original DSE archive not recovered** |
| agnostic top-20 illegal | Part-III frozen record | frozen claim record |
| candidate 759 vs 4087 | Part-III frozen record + Part-IV freeze | frozen claim record |
| stale-condition 0.329 / 10.61 | Part-III frozen record | frozen claim record |
| P1 p99 8.86e-4; 900/900 | Part-III frozen record | frozen claim record; raw replay unavailable |
| 9,000 required resets | `EXPERIMENT3_RTL_SEMANTICS.json` + final freeze | original frozen structured evidence |
| 10x condition ingress | Experiment 3/4 + final freeze | original frozen structured evidence |
| 8,990 stale uses / 8,999 illegal carries | Experiment 3 + final freeze | explicit stress-test evidence |
| +1 LUT / +0 FF generic controller | final freeze | frozen Yosys/ABC result |
| exact semantic RTL | `rtl/*.sv` | exact files, hash checked |
| PG2K400 294/252; 173/162; 2/2 | post-handoff JSON + resource screenshot | primary physical evidence |
| PG2K400 307.4085 MHz / +16.747 ns | post-handoff JSON + timing screenshot | primary physical evidence |

## Part-III qualification

The original Part-III generator/cost model, 4,096-row candidate archive, and
raw replay arrays were not recovered into this public release. The Part-III
summary is therefore suitable for **claim consistency/audit**, but not an
independent rerun of the historical DSE. `results/raw_part3/README.md` makes
that archival status explicit.

The included `compiler/reference_semantic_filter.py` is a transparent reference
implementation of legality filtering. It must not be described as a
reconstruction of the missing historical Part-III optimizer.

## Evidence chronology

The immutable Mac freeze predates the PG2K400 implementation, so its
`coverage.PG2K400_anchor_complete` remains false. The later board evidence is
stored separately rather than post-hoc editing the historical freeze.

## Non-claims

This artifact is not evidence for full-policy FPGA acceleration, a complete
12-mixer arithmetic datapath, board-level policy-action numerical correctness,
or cross-device performance portability.
