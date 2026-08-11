# EmbodiCore Current Claim Registry

This registry supersedes the **hardware-status wording** in the historical
pre-handoff `CLAIMS_PRE_HANDOFF.md`; it does not modify that frozen file.

## Supported

- 4,096 structural candidates; 3,664 resource-feasible at budget 0.80; 687
  legal+feasible.
- Candidate 759 is the frozen legal point; candidate 4087 is the matched
  agnostic negative control.
- Stale-condition mean action L2: 0.329 over 96 within-episode updates and
  10.61 over four sampled reset boundaries.
- P1 executed-action p99 L2: 8.86e-4; max: 1.29e-3; 900/900 under
  epsilon_a=0.10.
- 9,000 / 9,000 required scan resets.
- condition ingress: 4,608,000 B -> 460,800 B, 90% reduction / 10x ratio.
- no-reset stress: 8,990 stale-condition uses; 8,999 illegal scan carries.
- generic semantic-controller delta: +1 LUT / +0 FF versus Matched-NoReuse.
- PG2K400 physical anchor: self-test 294 LUT / 252 FF; condition ingress
  173 LUT / 162 FF; semantic controller 2 LUT / 2 FF.
- PG2K400 timing screenshot: 50.0000 MHz requested, 307.4085 MHz Fmax,
  +16.747 ns slack.

## Explicitly blocked

- 10x whole-policy or whole-accelerator speedup.
- 90% end-to-end latency reduction.
- full 12-mixer measured FPGA speedup.
- full Mamba accelerator area inferred from semantic-control logic.
- board-level policy-action correctness inferred from the self-test/LED.
- cross-device performance portability.
- Agnostic-4087 stress-test counts described as empirical episode-boundary
  statistics.

## Archival qualification

If original Part-III DSE/fidelity files are not recovered from the local
machine, the release ships a machine-readable frozen result record and labels
the raw-archive gap explicitly. It never fabricates raw candidate rows.
