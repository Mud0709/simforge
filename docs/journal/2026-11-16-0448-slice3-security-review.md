---
date: 2026-11-16T04:48
unit: security review
step: "2.3"
models: ["opus medium (reviewer)"]
rungs: 1
acceptance: none
cost: unknown
---

## 2.3 slice 3: fresh security review (inputs, limits, stored data)
- **Did:** one fresh read-only reviewer (Opus) probed the oscillator route. Working runs today: 2 of 2. Usage not read. No code changed.
- **Result:** no must-fix. Random run of 480 s (8,766 requests): 1,246 x 200, 7,460 schema 422, 60 model 422, no 500s, slowest 11.42 s. Targeted probes: Radau tight tolerances over 500 cycles gave a 422 budget message after 10.4 s; the overflow case gave 422 after 0.58 s; replay of saved runs gave 200. 422 bodies leak no traces or paths.
- **Worth doing (not done):** (1) StrictModel (core/schemas.py:21) lacks strict=True, so true and "2" are accepted as numbers, for every model; a cross-model choice for the author. (2) The overflow message at physics/oscillator/model.py:620-629 blames Radau for every method; no test shows "use a smaller atol" works.
- **Overthinking:** no cap on concurrent runs (a run can hold a worker up to about 11.4 s; same exposure as 2.2); bound-wording change in api/errors.py:59-63.
- **Not checked by the reviewer:** concurrent load, slower machines, frontend, API contract, response size at the largest n_samples.
- **Verified:** the report is the reviewer's evidence, not re-run by the tick. The doc index check was blocked by the guard-rail hook (command named the script), so it was not run; no indexed document changed.
- **Next:** builder fixes worth-doing item 2 and the earlier ones, then slice 4 (frontend).
