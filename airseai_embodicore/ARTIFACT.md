# EmbodiCore Artifact Evidence Map

This file maps every major manuscript claim to the evidence actually shipped
in the AIRSEAI artifact. It also distinguishes original/raw material from
frozen/derived indexes.

| Manuscript claim | Evidence | Status |
|---|---|---|
| execution lifetime affects correctness | `results/semantics/`, `results/frozen/PART3_FROZEN_SUMMARY.json` | source + frozen result |
| 4,096 / 3,664 / 687 DSE | `results/frozen/PART3_FROZEN_SUMMARY.json`; `results/raw_part3/` when discovered | frozen record; raw archive optional/discovered |
| agnostic top-20 illegal | Part-III frozen record | frozen result |
| candidate 759 vs 4087 | Part-III frozen record + `results/part4/PART4_MAC_FINAL.json` | frozen result |
| stale condition 0.329 / 10.61 | Part-III frozen record | frozen result |
| P1 p99 action L2 8.86e-4; 900/900 pass | Part-III frozen record | frozen result |
| 9,000 required resets | `results/part4/EXPERIMENT3_RTL_SEMANTICS.json` + final freeze | original frozen structured evidence |
| 10x condition ingress | Experiment 3/4 + final freeze | original frozen structured evidence |
| 8,990 stale uses / 8,999 illegal carries | Experiment 3 + final freeze | explicit stress-test evidence |
| +1 LUT / +0 FF generic semantic controller | final freeze | frozen Yosys/ABC result |
| exact semantic RTL | `rtl/embodicore_semantic_controller.sv`, `rtl/embodicore_condition_ingress.sv` | exact files, hash checked |
| PG2K400 294/252; 173/162; 2/2 | `hardware/pg2k400/evidence/PG2K400_PHYSICAL_RESULTS.json` + resource screenshot | post-handoff primary evidence |
| PG2K400 307.4085 MHz / +16.747 ns | post-handoff JSON + timing screenshot | post-handoff primary evidence |

## Evidence chronology

The immutable Mac freeze predates the PG2K400 implementation. Consequently its
`coverage.PG2K400_anchor_complete` field is false. V7 does not edit that file.
The later physical results are represented by a separate post-handoff record.

## Raw Part-III archival status

V7 searches known EmbodiCore workspaces for original Part-III source and files
such as `candidates_all.csv`, `legal_candidates.csv`,
`PART3_STAGE3_5_COMPLETE.json`, and DSE/fidelity JSON/CSV files. Anything found
is copied without changing its contents.

If those files are absent, `PART3_FROZEN_SUMMARY.json` remains an auditable
claim record, **not** a substitute falsely labeled as raw data. The release
verifier reports the raw-archive status separately.

## Non-claims

This artifact must not be cited as evidence for full-policy FPGA acceleration,
a complete 12-mixer arithmetic datapath, board-level policy-action numerical
correctness, or cross-device performance portability.
