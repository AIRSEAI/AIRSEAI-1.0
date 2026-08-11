# Evidence Status

Status for this release:

- **Claim-audit evidence:** PRESENT and machine-checked.
- **Part-I semantic source/results:** PRESENT.
- **Part-II trace utilities:** PRESENT.
- **Original Part-III source:** **NOT RECOVERED**.
- **Original Part-III raw DSE/fidelity results:** **NOT RECOVERED**.
- **Part-III frozen claim record:** PRESENT; explicitly derived/frozen, not raw.
- **Part-IV Mac frozen evidence:** PRESENT; immutable pre-handoff record.
- **Portable semantic/ingress RTL:** PRESENT; exact hashes checked.
- **PG2K400 pre-handoff package:** PRESENT; internal manifest checked.
- **PG2K400 post-handoff physical evidence:** PRESENT; screenshots/hash checked.
- **Fresh-checkout CI:** workflow provided at repository root and runs
  `airseai_embodicore/scripts/verify_release.sh` with Icarus Verilog installed.

The artifact therefore supports paper-claim auditing and several runnable
reference/source layers, but does not claim independent reproduction of the
historical Part-III DSE.
