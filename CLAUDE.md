# SimForge: working notes for Claude sessions

SimForge is **one scientific studio with three labs: Physics, Economy and Quant Research.**
No lab is "finished"; each is at an early stage. Read these before starting work:

- `ROADMAP.md`: the capability map for all three labs and the phased plan (the current step
  is marked 🔜). Keep every lab's eventual contents in mind, not just the next task.
- `ARCHITECTURE.md`: structure and decisions (pure scientific core, strict schemas, OpenAPI
  contract, shared `Workspace` layout, `record_run`, per-run checks).
- `SCIENTIFIC_VALIDATION.md`: what is proved, tested or only observed, per model.
- `docs/IB_FOUNDATIONS.md`: the additive IB Foundations track (see "Two tracks" below).
- `docs/LEARNING_GUIDE.md` (Physics Lab + shared engineering),
  `docs/ECONOMY_LEARNING_GUIDE.md` (Economy Lab) and `docs/QUANT_LEARNING_GUIDE.md`
  (Quant Research Lab).

## Two tracks (non-negotiable preservation rule)
- **Track B, the Advanced Simulation Studio**, is the roadmap's Phases 0-7 and capability map.
- **Track A, IB Foundations**, is an **additive** track of simpler, IB-aligned simulations
  (`docs/IB_FOUNDATIONS.md`, end of `ROADMAP.md`).
- Track A never replaces, removes, downgrades, reorders or indefinitely postpones any Track B
  item. Overlapping topics stay planned in Track B in full; the Track A module is a
  precursor. Do not rewrite the roadmap around Track A, and treat any instruction that seems
  to imply otherwise as needing explicit confirmation from the user.
- Track B is the primary sequence and progresses independently. Track A modules may be
  interleaved when practical, but are never prerequisites for, or gates on, any Track B step.

## Who you are working with
An IBDP1 student who wants to learn as the project grows. Explain decisions in short,
manageable chunks, give a learning checkpoint, and never just hand over code. Default to IB
level; build intuition before formulas.

## Standards (non-negotiable)
- Never present an approximation as exact. Label every result by how it was obtained.
- Keep mathematical guarantees, tests and empirical evidence separate and labelled.
- State assumptions and units. Validate inputs at the boundary; reject non-finite values.
- Tests use independent references (closed forms, limits, invariants, high-precision or
  independent methods), never the code's own output. Justify tolerances.
- Never fabricate or infer results: report only checks that were actually run.
- No authentication, paid APIs, secrets or speculative features.
- Extract a shared abstraction only when real models from at least two labs need it.

## Every task updates everything
Code, tests, `SCIENTIFIC_VALIDATION.md`, `ROADMAP.md` status, `ARCHITECTURE.md` and `README.md`
where affected, **and the relevant learning guide** (new chapter, checkpoints, exercises
without solutions). Guide excerpts are tagged `<!-- src: path:a-b -->` and must match the
files exactly; update line references when code moves.

## Git and GitHub
- Never push to `main`. Do not merge PRs, change repository settings or delete branches
  unless the user explicitly asks. Open a PR only when asked.
- One coherent, reviewable capability per PR.

## Checks
`scripts/check.sh --e2e` runs everything CI runs (ruff, mypy, pytest, API contract, ESLint,
Prettier, tsc, Vitest, build, Playwright). After changing backend schemas run
`make api-types` and commit the regenerated files.
