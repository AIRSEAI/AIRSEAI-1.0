# AIRSEAI-EmbodiCore PG2K400 Physical Anchor

This package contains the exact portable RTL frozen after the
EmbodiCore Mac experiments.

Target: PG2K400-6IFFBG676.

Top:
`rtl/embodicore_pg_selftest_top.sv`

The board experiment is deliberately minimal. It validates:

- synthesis / place-and-route,
- timing closure,
- physical execution of the frozen semantic-event self-test.

Expected functional counts:

- 900 policy-local condition loads,
- 9,000 scan resets,
- 900 condition-ingress transactions,
- 28,800 128-bit ingress beats.

A steady asserted `pass_led` means PASS.

Use the official board reference design for the PA-side 50 MHz clock,
user reset button, and user LED pin constraints. Do not guess pin IDs.

See `README_中文.md` for the complete procedure.
