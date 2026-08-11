# Audit and Reproducibility

## Guaranteed fresh-checkout path

```bash
bash scripts/verify_release.sh
```

This validates all evidence that is actually shipped. The GitHub Actions
workflow runs the same command on a fresh checkout and installs Icarus Verilog
so the portable PG self-test is compiled and simulated in CI.

## Independently rerunnable layers

- Minimal semantic-legality example: self-contained.
- Part-I semantic/source checks: rerunnable with the listed Python dependencies.
- Portable RTL PG self-test: rerunnable with Icarus Verilog.
- Claim audit of frozen Part-III and Part-IV records: self-contained.

## Part-II real-policy path

Trace collection utilities are shipped, but full real-policy replay requires
the upstream Mamba Policy software, the frozen checkpoint, and associated data.
Those large/external inputs are not embedded in ordinary Git history.

## Historical Part-III path

The original Part-III DSE source/results were **not recovered** into this
release. Consequently the public tree does not independently regenerate the
4,096 candidates, objective/cost ranking, or 900-invocation replay arrays.

`results/frozen/PART3_FROZEN_SUMMARY.json` is a machine-readable frozen claim
record derived from the previously frozen Part-III.5 result write-up. It is
not labeled raw evidence, and no synthetic 4,096-row table is generated.

If the original archive is recovered later, it should be added as a separately
identified provenance-preserving release update with hashes and an explicit
source-to-result command path.

## FPGA path

The exact pre-handoff RTL package is retained under
`hardware/pg2k400/pre_handoff/`; returned physical evidence is under
`hardware/pg2k400/evidence/`. Re-running place-and-route requires the vendor
PDS toolchain and corresponding device/board setup.
