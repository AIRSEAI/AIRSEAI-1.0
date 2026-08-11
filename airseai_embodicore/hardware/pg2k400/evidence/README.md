# PG2K400 post-handoff evidence

The pre-handoff package is preserved under `../pre_handoff/`. It contains the
exact RTL/self-test inputs and an immutable Mac freeze whose historical
`PG2K400_anchor_complete` field is false.

The files in this directory record the later physical implementation:

- `PG2K400_PHYSICAL_RESULTS.json` — machine-readable transcription;
- `pg2k400_resource_utilization.png` — vendor resource screenshot;
- `pg2k400_timing_summary.png` — vendor timing screenshot.

The screenshots are the primary returned physical evidence; the JSON exists so
the release verifier can check the paper-visible numbers without OCR.
