# Round 2 questions and rubrics (written before any agent ran)
Code: origin/claude/laughing-brahmagupta-50jkiy @ 7a7af47, paths relative to repo root.
Score = key points hit / key points; an ERROR (a false claim) is noted separately.

## Q1 impact: "If the output of `input_hash` (backend/src/simforge/core/reproducibility.py) changed format, what code paths, stored data and tests would be affected?"
K1 record_run computes and stores it for every run (api/recording.py:37).
K2 execute_run compares it with expected_input_hash; replay/recompute of every existing stored run would be refused with 409 (api/runs.py:126; replay.py:182, outputs.py:86).
K3 output_digest is defined as input_hash of the response (core/reproducibility.py:38), so every output digest changes too.
K4 golden digests break (tests/api/golden_runs.json / test_golden_digests.py) and test_registry.py:103.
K5 stored data: experiments table input_hash column + index (persistence/experiments.py:39,50); old records' hashes no longer match.

## Q2 thresholds: "Where are the oscillator's per-run check thresholds set, how is each threshold computed, and where else are oscillator limits enforced?"
K1 constants in physics/oscillator/model.py ~L145-155 (e.g. DISPLACEMENT_ERROR_FACTOR 50, DISPLACEMENT_ERROR_FLOOR 5e-9, VELOCITY 500/1e-9, ENERGY 2e4/1e-9, FREE_DECAY ..., ERROR_GROWTH_PER_CYCLE 1.0), mapped in _FACTORS.
K2 threshold() (model.py:343) = FACTOR (rtol+atol)(1 + growth*cycles) + FLOOR, used by _diagnostic/_checks.
K3 MAX_CYCLES = 500 (model.py:161), enforced in schemas.py (~L101) OscillatorParameters.
K4 input limits in analytical.py (MAX_QUALITY_FACTOR 1e4, OscillatorInputs.__post_init__) or other run guards (_guard stiffness, FREE_DECAY_MIN_MAXIMUM 1e-3).
K5 tests use their own independent threshold in tests/physics/oscillator_thresholds.py (test_oscillator_numerical.py calls it with a different signature).

## Q3 cross-layer: "Which frontend code calls the stored-run replay and recompute-outputs endpoints, and which backend functions handle each request, down to where the model is re-run?"
K1 client.ts replayExperiment (L149) used by ExperimentLog.tsx (L113).
K2 client.ts recomputeOutputs (L161) used by useReferenceRun.ts (L69).
K3 routes/experiments.py replay_experiment (L137) -> replay.replay_run; recompute_experiment_outputs (L144) -> outputs.recompute_outputs; both via _stored (repo.get).
K4 both call rerun.prepare_rerun (rerun.py:58) to rebuild entry+request.
K5 both call runs.execute_run with expected_input_hash (409 on mismatch).

## Q4 tests: "Which tests exercise the request-body size limit (BodySizeLimitMiddleware)?"
K1 tests/api/test_quant_api.py body-limit group (~L270-332: exact boundary, chunked boundary, CORS on 413, refused before parsing, chunked cut-off, small chunked works, other labs unaffected).
K2 test_quant_api.py:201/222 file-size tests relating MAX_FILE_BYTES to MAX_REQUEST_BYTES.
K3 tests/api/test_replay.py:216 oversized replay body 413.
K4 tests/api/test_run_outputs.py:216 oversized outputs body 413.
K5 no unit test of body_limit.py on its own (all via the app/TestClient).

## Q5 helper: "What does `_on_side` do, and who calls it and why?"
K1 defined physics/oscillator/analytical.py:262 (value, edge, side).
K2 nudges a rounded value by one ulp (nextafter) so it lies on the required side of the edge (or equals it when side 0).
K3 called only by derived() (analytical.py:248-249) for zeta (edge 1) and Q (edge 0.5).
K4 why: so zeta/Q never contradict the exact regime label decided from q with Fractions.

## Q6 name trap: "Where is `vacuum_optimum` defined and where is each definition used (src and tests)?"
K1 there are TWO different functions: physics/projectile/angle_sweep.py:92 (takes a ProjectileSetup) and physics/projectile/quadratic_angle_sweep.py:125 (takes v0, h, g).
K2 angle_sweep version used at angle_sweep.py:119 (within its module).
K3 quadratic version used at quadratic_angle_sweep.py:410 (run_angle_sweep).
K4 tests: tests/physics/test_quadratic_angle_sweep.py calls qas.vacuum_optimum many times (~8, incl. rejects-bad-inputs test L182); test_angle_sweep.py:82 only has it in a test name.
K5 neither is imported by another src module.

## Q7 structure: "List every model the API registry serves: entry name, HTTP route, and the function that computes it."
K1 seven entries in api/registry.py ENTRIES.
K2 PROJECTILE /physics/projectile/simulate -> projectile model.run; INTEGRATOR_STUDY /physics/projectile/integrators -> integrator_model.run; ANGLE_SWEEP /physics/projectile/angle-sweep -> projectile model.run_angle_sweep.
K3 QUADRATIC_DRAG /physics/projectile/quadratic-drag/simulate -> _quadratic_run -> quadratic_model.run; QUADRATIC_ANGLE_SWEEP /.../quadratic-drag/angle-sweep -> _quadratic_sweep_run -> quadratic_angle_sweep.run_angle_sweep.
K4 SOLOW /economy/solow/simulate -> solow model.run; DATASET_PROFILE /quant/datasets/profile -> profiling.run.
K5 the oscillator is not registered/served yet.

## Q8 errors: "What happens at the HTTP layer when a model raises `ModelDomainError`, and which models raise it?"
K1 compute_or_explain (api/runs.py:70-80) converts it (and DatasetError) to HTTP 422 with the message; SolverError -> 500.
K2 raisers in physics: projectile/model.py:173, integrator_model.py:150/156, quadratic_model.py:239, quadratic_angle_sweep.py:190/265.
K3 economy/solow/model.py:280/284.
K4 oscillator/model.py:264/584 (not served yet); quant raises DatasetError instead.

## Q9 frontend: "Where is a per-run validation check defined in the backend, and which frontend components render the checks?"
K1 ValidationCheck in core/schemas.py:69 (id, label, value, threshold, passed, kind, note).
K2 TS type via generated schema: lib/api/client.ts:30 (schema.d.ts).
K3 ChecksTable.tsx renders them.
K4 ChecksTable used by QuadraticDragResults, QuadraticAngleSweepPanel, SolowResults, QuantResults.
K5 the Phase 0 pages (linear projectile, integrators, linear angle sweep) do not show these checks (no ChecksTable).

## Q10 architecture: "Which backend modules are the most depended-on (imported by the most other modules), and what does each provide?"
K1 core.schemas is the top (≈24 src importers): StrictModel, ModelInfo, RunMetadata, ValidationCheck...
K2 core.errors (≈10): ModelDomainError, SolverError.
K3 persistence.experiments (≈8): ExperimentRecord/Repository.
K4 physics.projectile.schemas (≈9) and/or api.runs (≈7) named.
