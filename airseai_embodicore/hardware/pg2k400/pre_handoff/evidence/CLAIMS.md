# EmbodiCore Part IV Mac Evidence

## Supported claims

1. 900/900 recorded policy invocations have unique global conditions.
2. Policy-local condition reuse reduces trace-visible condition ingress from 4,608,000 B to 460,800 B over the frozen 900-policy workload.
3. This is a 90% reduction, or a 10x condition-ingress ratio.
4. The same 90% / 10x relation holds for generic 64-, 128-, 256-, and 512-bit serialized memory interfaces.
5. EmbodiCore-759 resets scan state on all 9,000 independent scan calls.
6. Under the explicit no-reset RTL stress test, Agnostic-4087 produces 8,990 stale-condition uses and 8,999 illegal scan carries.
7. The real-weight archive contains 108 arrays across all 12 mixers.
8. Dynamic workload measurements are available only for mixers 0, 6, and 11.
9. No additional strong policy-local intermediate was observed among the nine available real microtrace arrays.
10. At the frozen 128-bit / scan-rate-8 reference point, legal condition reuse reduces representative-kernel serialized cycles by about 0.005990%.
11. Across the frozen sensitivity sweep, the representative cycle effect ranges from 0.001375% to 0.012095%.
12. Relative to Matched-NoReuse, the verified EmbodiCore semantic controller adds one generic LUT and zero FFs under both 4-LUT and 6-LUT Yosys/ABC mappings.

## Claims that must NOT be made

1. 90% whole-accelerator latency reduction
2. 10x whole-policy speedup
3. full 12-mixer measured cycle speedup
4. full-accelerator area from the generic controller synthesis
5. PG2K400 LUT/FF utilization before PG implementation
6. device-measured latency before PG implementation
7. additional large policy-local intermediate reuse not observed in traces
8. Agnostic-4087 stress-test counts as empirical dataset episode statistics

## Hardware status

- Primary semantic and traffic evidence: complete on Mac.
- Portable semantic-controller RTL: verified.
- Generic Yosys/ABC synthesis: complete.
- PG2K400 physical anchor: pending and optional to the primary claims.
