---
date: 2026-11-10T03:47
unit: TDD slice
step: "2.3"
models: ["opus high (builder)", "opus high (reviewer)"]
rungs: 1
acceptance: pass
cost: unknown
tests_passed: 250
tests_failed: 0
tests_skipped: 0
tests_flaky: 0
test_seconds: 36.92
checks:
  - "mypy: pass"
  - "pytest_osc: pass"
  - "ruff: pass"
---

## 2.3 slice 2 built (numerical.py, model.py, schemas.py); fresh review found no must-fix
- **Did:** builder implemented the slice and set the measured thresholds in the helper's builder block; fresh review done; one false doc claim corrected. Working-run commits since the work-limit sha: 2 of 6 before this commit.
- **Usage:** usage not read; today's working runs: 1 of 2 before this commit.
- **Subagents:** builder (opus, high, rung 1, acceptance passed first time); reviewer (opus, high; no must-fix, 7 worth-doing, 1 false doc claim). 2 of 4 used.
- **Checks run:** pytest on the two test files (250 passed), ruff check, mypy, doc_index --check. The builder also ran ruff format --check and the full backend pytest (2338 passed): reported, not re-run here.
- **Verified:** test-file hashes unchanged (numerical 7a3b134d, model 7be2fba1); helper changed only in its builder block (1ce0e277, per builder and reviewer); acceptance commands re-run by this run. Review check: the reviewer re-derived the scaled equations and V = omega0*X independently. Check 5 of Acceptance ("git diff prints nothing") literally prints the helper (allowed edit). Acceptance check 6 (fresh review) is done.
- **Decisions taken for you:** N_MAX = 500 (D6 said 1000, measured at default settings; reverse: N_MAX and MAX_CYCLES); thresholds F=50/500/2e4/1e3/20 with growth G=1 (reverse: edit constants); free-decay checks omitted when second maximum < 1e-3 X; limits live in schemas.py only; energy factor 2e4 driven by omega=100*omega0 (alternative: normalise by kX^2 max(1,w/w0)^2, needs a test change).
- **Review findings left for slice 3 (worth-doing):** (1) worst-case run times unmeasured: RK45 at the tightest pair 500 cycles 22 s and 388 MB, Radau tightest pair ~5 min, so a per-method cost rule is needed; (2) tightest-pair/long/fast-drive corner has margin 4.6x not 10x (doc claim corrected); (3) free-decay thresholds scale with the whole run's cycles though they use the first two maxima; (4) omega counts when F0 = 0, wrongly refusing or loosening free runs; (5) the 241-point resonance curve misses a high-Q peak when omega > 2.5 omega0; (6) free-decay switching uses the computed maxima, not exact ones, and the user is not told; (7) X can exceed the motion by zeta for heavily damped runs with v0. Stale docstring in the helper (lines 21-34) says provisional N_max = 1000.
- **Waiting for you:** see docs/HANDOFF.md, Open decisions (the Radau/cost rule blocks slice 3).
- **Next:** author decides the cost rule; then a slice 2 fix unit for items 2-6 (or fold into slice 3), then slice 3 (endpoint, corners test).
