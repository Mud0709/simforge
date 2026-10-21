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
The author, an IBDP1 student, directs the project and writes the prompts; understanding the
software, the science and the decisions is an explicit goal alongside quality. Default to IB
level; build intuition before formulas, without oversimplifying the real reasoning.
- Explain decisions in short, manageable chunks; never just hand over code. Give a learning
  checkpoint (a question or two) after new concepts.
- End every meaningful investigation, implementation or review with a short **"What this
  means for me"**: what changed or was found, why it matters, the key concept, the main
  trade-off or limitation, and what to do next.
- Put significant decisions to the author *before* implementing, with alternatives and
  trade-offs. Recommend with reasons; do not decide silently or enlarge the task.
- Help sharpen prompts: goal, context, scope, acceptance criteria, risks.
- When the author doesn't understand something, stop and teach it with a small example.
- After a milestone: a status report; after a merge: a draft learning-log entry for
  `docs/LEARNING_LOG.md`, added only once the author approves it, in the branch of their next
  change (skill `simforge-status`). Separate verified facts from assumptions.

## Skills (project skills live in `.claude/skills/`; see `SOURCES.md` there)
End each response with **"Recommended skill for the next step"**: name the one that fits
(or "none needed") and say why in a few words. Skills marked *(account)* come from the
author's Claude account, not this repository; if one is not available in a session, say so
and recommend the closest available alternative.

| Situation | Skill |
|---|---|
| Returning after a break; status report; learning-log entry | `simforge-status` |
| Stress-testing a plan, prompt or design decision | `grilling` |
| Any bug, failing test or unexpected behaviour (before proposing a fix) | `systematic-debugging` |
| Building a feature or fixing a bug test-first | `tdd` |
| Before claiming anything is done, fixed or passing | `verification-before-completion` |
| Reviewing a diff or PR for bugs | `/code-review` (built-in) |
| Changes touching uploads, inputs, limits or stored data | `/security-review` (built-in) |
| Tidying a finished change (quality, not bugs) | `/simplify` (built-in) |
| Seeing a change in the running app, screenshots | `run` (built-in) |
| Learning a concept in depth | `anthropic-skills:learn` *(account)* |
| Research across many sources (methods, literature) | `anthropic-skills:deep-research` *(account)* |
| Checking an analysis or statistics before trusting it (Quant Lab) | `data:validate-data`, `data:statistical-analysis` *(account)* |
| Designing charts | `dataviz` *(account)* |
| Writing or changing a skill | `anthropic-skills:skill-creator` *(account)* |
| Broad codebase searches without filling the context | the `Explore` subagent (not a skill) |

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
