# EmbodiCore Part I — Apple Silicon / v11-aligned

Purpose:
1. Audit the official Mamba Policy and state-spaces/mamba source.
2. Materialize the v11 execution contract:
   C(z) = <lifetime, reset_event, update_event, legal_reuse_scope>.
3. Run pure-PyTorch numerical tests on CPU and Apple MPS.
4. Demonstrate:
   - legal policy-local reuse is numerically equivalent;
   - illegal selective-scan state carry across independent calls changes computation;
   - stale policy-local condition reuse after a new observation changes computation.
5. Package all evidence into `part1_semantics.zip`.

This starter deliberately DOES NOT install `mamba-ssm`, CUDA, Triton, Vitis, or a simulator.
The official repositories are used for source audit only.

Run from the workspace root:
    bash part1/run_all.sh
