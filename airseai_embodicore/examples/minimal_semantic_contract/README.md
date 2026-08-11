# Minimal semantic-contract example

This example demonstrates the central EmbodiCore idea without requiring a
model checkpoint, robot simulator, GPU, or FPGA.

Run:

```bash
bash scripts/run_sample.sh
```

The example defines:

- `scan_state` with maximum legal lifetime `scan`;
- a condition with maximum legal lifetime `policy`.

It then checks three simplified design points:

- `Matched-NoReuse`: legal;
- `EmbodiCore-759`: legal;
- `Agnostic-4087`: illegal because it extends both lifetimes to `episode`.

The example is intentionally small. It teaches the semantic-legality interface;
it is not a performance benchmark.
