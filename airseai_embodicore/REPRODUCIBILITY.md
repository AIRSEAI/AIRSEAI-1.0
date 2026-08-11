# Reproducibility

## Fast path

```bash
bash scripts/verify_release.sh
```

This is self-contained and verifies the shipped frozen evidence and claim
boundaries.

## Semantic/source path

Part-I semantic code is under `semantics/`; Part-II trace collection utilities
are under `tracing/`. Full real-policy replay requires the upstream software,
checkpoint, and data whose provenance/hashes are recorded separately.

## Raw Part-III path

If V7 discovers the original Part-III archive, it is copied under
`results/raw_part3/` and the original source under `compiler/original/` /
`fidelity/original/`. Absence of that archive is reported, never hidden.

## FPGA path

The exact handoff package used for PG2K400 is retained under
`hardware/pg2k400/pre_handoff/`. The returned physical evidence is under
`hardware/pg2k400/evidence/`. Vendor software is required to regenerate
placement-and-routing reports.
