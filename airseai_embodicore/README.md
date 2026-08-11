# AIRSEAI EmbodiCore

**AIRSEAI EmbodiCore** is a semantics-aware hardware compilation and reproducibility artifact for **stateful embodied AI**.

Its core idea is simple:

> **Execution semantics determine what hardware transformations are behaviorally legal; hardware constraints determine which legal implementation is physically feasible and preferable.**

EmbodiCore is designed for embodied-AI policies whose execution extends beyond a single stateless model call. Examples include policies with recurrent state, selective-scan state, iterative denoising, observation-conditioned context, policy-local caches, or other state whose legal lifetime depends on the control loop.

This folder provides a clean, open-source reference implementation of that idea under the AIRSEAI project.

---

## 1. Why EmbodiCore exists

Traditional model compilers typically optimize a computational graph: fuse operators, change precision, reuse memory, alter placement, or increase parallelism.

For stateful embodied AI, this is not enough.

A transformation may be computationally efficient and still be behaviorally wrong if it:

- carries state across an illegal execution boundary;
- reuses a condition after a new observation arrives;
- changes the lifetime of policy-local or denoising-local state;
- passes tensor-level numerical checks but changes the final action.

EmbodiCore therefore inserts a semantic legality layer before hardware optimization.

Conceptually:

```text
Policy execution
      ↓
Execution contract
      ↓
Semantic legality analysis
      ↓
Legal hardware design space
      ↓
Resource / performance optimization
      ↓
Portable RTL
      ↓
Action-boundary verification
```

The execution domains used by the current artifact are:

```text
scan ⊂ denoise ⊂ policy ⊂ episode
```

---

## 2. What this folder contains

The intended public structure is:

```text
airseai_embodicore/
├── README.md
├── CITATION.cff
├── THIRD_PARTY.md
├── REPRODUCIBILITY.md
├── PROVENANCE_REVIEW.md
├── MANIFEST.sha256
├── .gitignore
│
├── semantics/
│   └── execution contracts and semantic tests
│
├── tracing/
│   └── real-policy trace collection utilities
│
├── compiler/
│   └── legality analysis and design-space exploration
│
├── fidelity/
│   └── numerical and action-boundary fidelity checks
│
├── rtl/
│   ├── portable SystemVerilog
│   └── testbench/
│
├── experiments/
│   └── mac/
│       └── reproducibility experiments
│
├── results/
│   ├── semantics/
│   ├── dse/
│   ├── fidelity/
│   └── part4/
│
├── hardware/
│   └── pg2k400/
│       └── minimal physical-anchor experiment
│
├── examples/
│   └── minimal_semantic_contract/
│
├── scripts/
│   ├── run_sample.sh
│   ├── verify_frozen_results.py
│   └── verify_release.sh
│
├── requirements/
└── release_assets/
```

The public tree is intentionally curated. It should **not** contain Python virtual environments, checkpoints, vendored third-party repositories, raw training datasets, nested Git repositories, or large unpublished experiment dumps.

---

## 3. Quick start

### 3.1 Requirements

For the smallest CPU-only example:

- Python 3.9+
- NumPy

For RTL simulation:

- Icarus Verilog

For generic technology-independent RTL synthesis:

- Yosys + ABC

The full real-policy reproduction path additionally requires the upstream policy/model software described in [`THIRD_PARTY.md`](THIRD_PARTY.md).

---

## 4. Run the smallest sample

The recommended first command is:

```bash
cd airseai_embodicore
bash scripts/run_sample.sh
```

This sample is intentionally small. It does **not** require the original policy checkpoint, CUDA, a robot simulator, or an FPGA.

It demonstrates the central EmbodiCore abstraction:

1. define execution domains;
2. define state/condition lifetimes;
3. compare a legal policy-local reuse strategy with an illegal cross-policy reuse strategy;
4. verify that the legality checker accepts the former and rejects the latter.

Expected final output:

```text
AIRSEAI EmbodiCore minimal sample
--------------------------------
Matched-NoReuse : LEGAL
EmbodiCore-759  : LEGAL
Agnostic-4087   : ILLEGAL

Semantic legality check: PASS
```

This example is the fastest way to understand what EmbodiCore adds beyond a conventional graph compiler.

---

## 5. Verify the frozen paper evidence

After the full artifact has been populated, run:

```bash
python3 scripts/verify_frozen_results.py
```

Expected headline checks include:

```text
EmbodiCore frozen evidence: PASS
condition traffic reduction : 90.000%
condition traffic ratio     : 10.000x
scan resets                 : 9000/9000
semantic controller overhead: +1 LUT, +0 FF
full 12-mixer cycle claim   : BLOCKED
```

The purpose of this verifier is not to rerun model training. It checks that the structured evidence shipped with the repository is internally consistent with the frozen claims.

---

## 6. Reproduce the main experimental layers

EmbodiCore separates reproducibility into several layers.

### Layer A — Semantic contracts

```bash
cd semantics
bash run_all.sh
```

This layer tests execution-lifetime rules such as:

- scan-local state;
- denoise-local state;
- policy-local conditions;
- illegal stale-condition reuse;
- illegal cross-boundary state carry.

### Layer B — Real-policy tracing

See:

```text
tracing/
```

This layer collects policy-level and representative mixer-level traces from the real policy implementation.

It may require external software and checkpoints. These dependencies are deliberately not silently redistributed.

### Layer C — Compiler / DSE

See:

```text
compiler/
```

This layer constructs and filters candidate hardware configurations.

The central rule is:

```text
resource feasible ≠ semantically legal
```

A candidate is optimized only after it passes the semantic legality filter.

### Layer D — Fidelity

See:

```text
fidelity/
```

This layer checks numerical transformations at the policy-action boundary.

The current frozen mixed-precision point is:

```text
P1:
FP16 weights / activations
FP32 scan state / accumulation
```

### Layer E — Portable RTL

See:

```text
rtl/
```

The current portable RTL includes semantic lifetime/reset control and condition ingress.

Typical commands:

```bash
iverilog -g2012 ...
vvp ...
```

Technology-independent synthesis can be run with Yosys/ABC.

### Layer F — Physical FPGA anchor

See:

```text
hardware/pg2k400/
```

This is intentionally a minimal board experiment. Its purpose is to verify that the same portable RTL can be synthesized, placed, routed, and executed on a real FPGA.

It is **not** intended to claim a full-policy FPGA speedup.

---

## 7. Current frozen results

The current artifact supports the following headline results.

### Semantic legality

At the frozen 0.80 resource budget:

```text
Total structural candidates       : 4096
Resource-feasible candidates      : 3664
Feasible + semantically legal     : 687
```

Therefore, approximately **81.2% of resource-feasible candidates are semantically illegal**.

This is the main architectural result: a hardware optimizer that ignores execution semantics can optimize into the wrong design space.

### Legal condition reuse

Across the frozen 900-policy workload:

```text
Matched-NoReuse condition ingress : 4,608,000 B
EmbodiCore-759 condition ingress  :   460,800 B
Reduction                         : 90%
Ratio                             : 10x
```

This is a **condition-ingress traffic** result, not a whole-accelerator speedup claim.

### RTL semantic behavior

The frozen RTL experiment observes:

```text
EmbodiCore scan resets            : 9000 / 9000
Agnostic stale-condition uses     : 8990
Agnostic illegal scan carries     : 8999
```

The agnostic counts come from an explicit no-reset RTL stress test; they are not presented as empirical episode statistics.

### Generic semantic-control cost

Relative to the matched legal baseline:

```text
EmbodiCore semantic controller:
+1 generic LUT
+0 flip-flops
```

The same delta appears under both generic 4-LUT and 6-LUT Yosys/ABC mappings.

These are technology-independent logic mappings, not vendor-specific PG2K400 resource counts.

### Representative cycle effect

The legal condition reuse has only a small representative whole-kernel cycle effect:

```text
Reference point : ~0.00599%
Sensitivity     : ~0.00137% – 0.01210%
```

This negative result is intentional and important: **EmbodiCore is primarily a semantics/legality contribution, not a manufactured speedup claim.**

---

## 8. How to extend EmbodiCore

EmbodiCore is meant to be extended at the level of **execution semantics**, not by hard-coding one model architecture.

A new backend or policy should usually be added in four steps.

### Step 1 — Define the execution domains

For example:

```text
token
scan
denoise
policy
episode
mission
```

Only add domains that are meaningful to the target policy.

### Step 2 — Define a lifetime contract

For every reusable or stateful object, describe:

```text
object
lifetime
reset boundary
reuse boundary
precision requirement
```

Conceptually:

```python
contract = {
    "scan_state": {
        "lifetime": "scan",
        "reset_on": "scan_start",
    },
    "global_condition": {
        "lifetime": "policy",
        "invalidate_on": "observation_update",
    },
}
```

### Step 3 — Add legality rules

A transformation should answer:

```text
Does this transformation extend an object's lifetime?
Does it reuse data after its invalidation boundary?
Does it merge two execution contexts that must be independent?
```

If yes, the candidate must be rejected before performance ranking.

### Step 4 — Add a physical backend

Once a candidate is semantically legal, a backend may choose:

- FPGA mapping;
- ASIC mapping;
- NPU mapping;
- GPU kernel structure;
- SRAM/DRAM placement;
- banking;
- parallelism;
- operator fusion;
- legal mixed precision.

The important separation is:

> **Semantics defines legality. The backend defines feasibility and preference.**

---

## 9. Adding another embodied-AI policy

A new policy integration should ideally provide:

```text
integrations/<policy_name>/
├── README.md
├── contract.json
├── trace_adapter.py
├── legality_rules.py
├── expected/
└── tests/
```

The integration README should explain:

1. what constitutes one policy invocation;
2. which internal states persist;
3. which states reset;
4. which conditions change with a new observation;
5. where actions are published;
6. what numerical error metric is evaluated at the action boundary.

A policy integration should avoid modifying the generic compiler unless the new policy exposes a genuinely new semantic concept.

---

## 10. Adding another hardware backend

A backend should live under:

```text
backends/<backend_name>/
```

and implement, conceptually:

```text
legal candidate
     ↓
resource model
     ↓
mapping
     ↓
RTL / kernels / configuration
     ↓
physical feasibility
```

Examples:

```text
backends/pg2k400/
backends/generic_rtl/
backends/asic/
backends/gpu/
```

Backend-specific constraints must not silently change the execution contract.

If a device cannot implement a legal candidate, the correct result is:

```text
LEGAL but PHYSICALLY INFEASIBLE
```

not:

```text
SEMANTICALLY ILLEGAL
```

This distinction is fundamental to EmbodiCore.

---

## 11. How EmbodiCore can help other AIRSEAI projects

EmbodiCore is useful wherever an embodied-AI system contains state or reusable context whose correct lifetime is defined by the robot/control loop.

Potential uses include:

### Robot policy deployment

Before compiling a policy onto an accelerator, EmbodiCore can prevent illegal cross-step or cross-observation reuse.

### Multi-modal embodied models

Vision, language, proprioception, maps, memory, and task context may each have different valid lifetimes. EmbodiCore provides a common vocabulary for describing them.

### World-model / planning systems

Planner state, rollout state, environment state, and policy state need not share the same lifetime. A semantic contract can prevent them from being accidentally fused.

### Multi-agent systems

Agent-local, team-local, task-local, and episode-local state can be modeled as different execution domains.

### Edge AI accelerators

A compiler can first determine the legal reuse/memory space and then optimize SRAM residency, bandwidth, banking, precision, and parallelism.

### Dataset and benchmarking infrastructure

Trace datasets can record execution-boundary metadata in addition to tensors, making them more useful for hardware/software co-design.

---

## 12. Using EmbodiCore as a library concept

EmbodiCore is not limited to one monolithic compiler.

Other projects can reuse only the semantic interface:

```python
from embodicore import ExecutionContract, LegalityChecker

contract = ExecutionContract(...)
checker = LegalityChecker(contract)

if checker.is_legal(candidate):
    backend.compile(candidate)
```

The current repository is a research artifact rather than a stable packaged Python SDK, but this API direction is intentional.

Projects should depend on the semantic abstraction rather than on experiment-specific file paths.

---

## 13. Contribution guidelines

A contribution should ideally include:

- a clear semantic concept;
- a machine-readable contract or configuration;
- a legality test;
- one positive test;
- one negative test;
- reproducible structured results;
- no hidden dependency on a private checkpoint or local path.

For hardware contributions, also include:

- portable source where possible;
- simulation testbench;
- synthesis instructions;
- explicit distinction between generic and vendor-specific results.

For new result claims, add them to the structured results and update the claim registry rather than editing README numbers manually without evidence.

---

## 14. Claim discipline

EmbodiCore deliberately distinguishes what is supported from what is not.

Supported examples:

```text
semantic legality changes the design space
legal condition reuse reduces condition ingress
action-boundary mixed precision passes the frozen threshold
portable semantic-control RTL has very small generic logic cost
```

Unsupported examples:

```text
90% whole-accelerator speedup
10x whole-policy speedup
full 12-mixer measured dynamic cycle speedup
PG2K400 resource counts before physical implementation
```

See:

```text
results/part4/CLAIMS.md
```

for the frozen machine-auditable claim boundary.

---

## 15. Third-party code and large research data

This folder should not vendor full third-party repositories by default.

See:

```text
THIRD_PARTY.md
release_assets/OMITTED_DATA_SHA256.txt
```

for upstream provenance and hashes of intentionally omitted data.

Before publishing checkpoints, raw traces, extracted weights, or datasets as release assets, verify redistribution rights separately.

---

## 16. Release verification

Before committing or opening a pull request, run:

```bash
bash scripts/verify_release.sh
```

The release verifier checks:

1. required project documentation;
2. expected directory structure;
3. minimal sample execution;
4. frozen paper evidence;
5. RTL source presence;
6. absence of virtual environments, checkpoints, nested Git repositories, and raw unpublished model data;
7. large files;
8. high-confidence secret patterns.

A release candidate should finish with:

```text
AIRSEAI EmbodiCore release verification: PASS
```

---

## 17. Citation

If you use EmbodiCore, please cite the associated EmbodiCore paper and the AIRSEAI software artifact.

See:

```text
CITATION.cff
```

---

## 18. Project status

The current repository should be considered a **research reference implementation and reproducibility artifact**.

The intended long-term direction is to evolve EmbodiCore into a reusable semantics layer that can sit between embodied-policy runtimes and multiple hardware/compiler backends.

The key design rule should remain stable:

> **First determine what is behaviorally legal. Then optimize the hardware.**

---

## Core rule

> **Execution semantics determine what is behaviorally legal; hardware constraints determine what is physically feasible and preferable within the legal set.**
