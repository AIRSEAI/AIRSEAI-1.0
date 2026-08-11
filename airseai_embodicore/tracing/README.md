# EmbodiCore Part II — Real Mamba Policy Traces

Goal
----
Collect real-checkpoint traces from the official Mamba Policy implementation
without modifying the upstream repository.

Part II establishes:
1. the trace collector is equivalent to the official `predict_action`;
2. real Mamba-Policy denoising traces for Part III compiler/fidelity replay;
3. real-checkpoint action sensitivity to an invalid stale observation condition.

It does NOT yet claim:
- illegal selective-scan-state carry at full-policy action level;
- Contract-Agnostic-DSE ranking;
- FPGA latency/traffic/energy;
- closed-loop task success.

Expected Linux workspace
------------------------
$EMBODICORE_ROOT/
  third_party/
    Mamba-Policy/
  part2/
  part2_results/

The official repository currently documents training/evaluation but does not
advertise a downloadable pretrained policy checkpoint in its README. The
runner therefore requires a real `.ckpt` produced by the official training
pipeline.

Recommended primary workload
----------------------------
Mamba-V1 / Adroit Pen.

Paper protocol
--------------
`n_action_steps` is forced to 3 during tracing to match the published IROS
protocol. The checkpoint's original value is preserved in the manifest.

Outputs
-------
part2_results/
  environment.json
  checkpoint_manifest.json
  trace_manifest.json
  trace_equivalence.csv
  real_policy_traces.npz
  mixer_microtraces.npz
  stale_condition_action_error.csv
  summary.txt
  source_audit.txt

The packaging script creates:
  part2_real_traces.zip
