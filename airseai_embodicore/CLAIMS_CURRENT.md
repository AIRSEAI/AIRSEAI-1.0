# EmbodiCore Current Claim Registry

This registry supersedes hardware-status wording in the historical pre-handoff
record without modifying that frozen file.

## Supported by shipped evidence

- Source-level semantic necessity and negative controls under `results/semantics/`.
- Frozen Part-III record: 4,096 structural candidates; 3,664 resource-feasible
  at budget 0.80; 687 legal+feasible.
- Frozen candidate identities: legal 759; matched agnostic 4087.
- Frozen stale-condition action record: 0.329 over 96 within-episode updates;
  10.61 over four sampled reset-boundary comparisons.
- Frozen P1 action record: p99 8.86e-4; max 1.29e-3; 900/900 under
  epsilon_a=0.10.
- RTL evidence: 9,000/9,000 required scan resets; condition ingress
  4,608,000 B -> 460,800 B; explicit no-reset stress counts 8,990/8,999.
- Generic semantic-controller delta: +1 LUT / +0 FF versus Matched-NoReuse.
- PG2K400 physical anchor: 294/252 self-test top, 173/162 ingress, 2/2
  semantic controller; 50 MHz requested, 307.4085 MHz Fmax, +16.747 ns slack.

## Evidence qualification

The DSE and action-fidelity values above are **supported as frozen claim
records**, not as independently regenerated results from the current public
checkout. Original Part-III source/raw result files were not recovered.

## Explicitly blocked

- Claiming the frozen Part-III summary is raw DSE evidence.
- Claiming the reference semantic filter reconstructs the historical Part-III
  optimizer/cost model.
- 10x whole-policy or whole-accelerator speedup.
- 90% end-to-end latency reduction.
- Full 12-mixer measured FPGA speedup.
- Full Mamba accelerator area inferred from semantic-control logic.
- Board-level policy-action correctness inferred from the self-test/LED.
- Cross-device performance portability.
- Agnostic-4087 stress-test counts described as empirical episode-boundary
  statistics.
