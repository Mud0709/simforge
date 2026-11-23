# Track A plan, module A2: momentum, impulse and collisions

Written on 2026-11-21 by the `planner`. The first Track A (IB Foundations) module ever built.
Inputs: `docs/IB_FOUNDATIONS.md` P3 (lines 330-372), "Syllabus sources and their limits"
(35-70), "Model identities vs claims" (71-93), "Product structure (proposed)" (510-522);
`ROADMAP.md` Track A (138-170) and the capability map's Collisions row; `ARCHITECTURE.md`
decisions 10-12 and "Adding a new model"; the author's request of 2026-11-21 (chat): "Plan A2
momentum and collisions as the next IB module. Write a separate learning guide to start with
the code as well. Ensure that I learn the basics and that you don't leave it completely on me
to code as I don't have much prior coding knowledge."

**Review before building:** the plan touches the scientific core, so 3 `reviewer`s (angles
a, b, c of the autopilot skill, step 3) in a planning-only session.

## Slice status
| Slice | Who writes the code | Status |
|---|---|---|
| S0 Sitting 0: set-up on the author's laptop, first green test | Claude: skeleton, stubs, tests, guide ch. 0-5 · **Author: install, clone, `momentum` (worked example), first commit and push** | ⏳ |
| S1 Sitting 1: energy and totals | Claude: tests, guide ch. 9 · **Author: 4 functions** | ⏳ |
| S2 Sitting 2: the 1-D collision | Claude: tests, guide ch. 6-8, 10 · **Author: 1 function + guards; `kinetic_energy` made exact if needed** | ⏳ |
| S3 Sitting 3: impulse, force and explosions | Claude: tests, guide ch. 11 · **Author: 4 functions** | ⏳ |
| S4 The 1-D model and its API | Claude (risky) | ⏳ |
| S5 The SL page, `/foundations` index and animation | Claude (routine) | ⏳ |
| S6 Sitting 4 (HL): 2-D momentum | Claude: tests, guide ch. 12 · **Author: 3 functions** | ⏳ |
| S7 The HL 2-D case: API and view | Claude (risky API part) | ⏳ |
| S8 Physics guide part, docs and close-out | Claude (routine) | ⏳ |

## Scope
**In:** IB Physics A.2 momentum content with A.3 energy comparisons: 1-D two-body collisions
(elastic, inelastic, perfectly inelastic), 1-D explosions, impulse and average force, a
force-time graph, and 2-D collisions for HL (momentum by components). One model,
`physics.foundations.collisions` v1.0.0; one endpoint; the page
`/physics/foundations/collisions`; the `/foundations` index; the coding guide
`docs/FOUNDATIONS_CODING_GUIDE.md`; a short physics "Foundations" part in
`docs/LEARNING_GUIDE.md`.
**Out:** everything Track B owns. Phase 4 (2-D discs, event-driven simulation, bookkeeping,
animation) and 4b stay planned in full and unchanged; this module is their precursor and
neither depends on the other. Step 2.6 (animation) keeps its full scope: A2's animation is a
local, minimal component, not a shared animation layer. **Track B order:** 2.4 is done; A2 is
interleaved between 2.4 and 2.5 at the author's choice (2026-11-21); 2.5 stays the next Track
B step and is not reordered, merged or dropped (see D14 for the time limit).

## Before deciding
1. **What a professional would do that a naive plan would not.** (a) Compute the kinetic
   energy lost from the closed form `½μ(1 − e²)(u1 − u2)²`, not as a difference of two large
   energies: near e = 1 the difference cancels to rounding noise. Show both, labelled, and
   make their agreement a check. (b) Check the model with exact rational arithmetic: every
   formula here uses only + − × ÷, so the same Python functions run on `fractions.Fraction`
   and the identities (momentum, restitution, energy loss, frame independence) hold
   **exactly**, with no tolerance at all; floats get a stated rounding allowance. (c) Test the
   frame independence (a Galilean boost: add w to every velocity; momentum shifts by
   (m1 + m2)w, the energy loss does not change), which catches sign and index errors that
   single examples miss. (d) Separate what the guide requires from modelling choices: e, the
   force-pulse shape and the animation are choices, labelled in the UI. (e) Refuse inputs
   that are not a collision (bodies moving apart: u1 ≤ u2 with body 1 on the left) instead of
   returning numbers for an event that never happens. (f) For a learner, keep the code the
   learner writes free of frameworks: pure functions, stdlib only.
2. **Raw material.** The P3 entry (equations, identities, controls); the existing model
   pattern (`ModelEntry`, `execute`, `api/registry.py`, golden runs in
   `tests/api/test_registry.py`, `ChecksTable`, `AssumptionsList`, `Workspace`, `spec()` in
   `lib/fields.ts`); the discriminated-union precedent in `quant/profiling/schemas.py`
   (`kind: Literal["upload"] | Literal["sample"]`); `tests/approx.py` `rel_approx`;
   `ModelDomainError` (`core/errors.py`, a `ValueError` subclass); the experiment log's lab
   filter, which keeps model ids starting with `<lab>.` (`persistence/experiments.py:213`),
   so the id must start with `physics.`.
3. **Methods and tools.** Python stdlib (`fractions`, `math.fsum`, `math.hypot`), Pydantic,
   pytest, Plotly (already loaded lazily), SVG and `requestAnimationFrame` for the animation.
   No new dependency (`backend/pyproject.toml`: fastapi, uvicorn, pydantic, numpy, scipy;
   nothing is added).
4. **What proves it right, other than Claude saying so.** Closed forms and identities checked
   in exact arithmetic: a scratch run on 2026-11-21 (`fractions`, 2000 random cases with
   e ∈ {0, 0.1, …, 1}) confirmed exactly: momentum conserved; `v2 − v1 = −e(u2 − u1)`; the
   loss formula; `J = m1(v1 − u1) = −m2(v2 − u2)`; boost invariance of the loss and of the
   outcome. Hand-worked examples (checked in the same run): equal masses, e = 1, (2, 0) →
   (0, 2); m = (1, 3), e = 1, (4, 0) → (−2, 2); m = (2, 3), e = 0, (5, 0) → (2, 2); explosion
   m = (1, 3) from rest, v1 = −3 → v2 = 1, 6 J released (= ½·1·3² + ½·3·1²); 2-D, equal masses, u1 = (4, 0),
   u2 = 0, v1 = (2, 2) → v2 = (2, −2), kinetic energy 8 J before and after, at 90° (by hand).
   The force-pulse area: the trapezoid rule on a half-sine with n intervals gives exactly
   `J·(h/2)cot(h/2)`, h = π/n (proved: the sum Σ sin kh = cot(h/2)), so the per-run area check
   has an exact expected value, not a tolerance guess.

## Syllabus re-check (what this plan relies on)
Relied on, all from P3 and recorded in `IB_FOUNDATIONS.md` as **verified** (A.1-A.5 were read
line by line from the author's copy of the *Physics guide, first assessment 2025*, on
2026-10-16): conservation of linear momentum; impulse `J = FΔt`; `F = Δp/Δt`; elastic and
inelastic collisions of two bodies; explosions; energy considerations; "one-dimensional for
SL and two-dimensional for HL"; simultaneous momentum-and-energy equations not required;
energy comparisons use A.3 (`Ek = ½mv²`, P4 line 382).
**Not re-checked in this session:** the guide copy is not in the repository or on this
machine (searched 2026-11-21), so the pre-build re-check `IB_FOUNDATIONS.md` requires cannot
be done here. **Author confirmation (before S5's UI text):** read the A.2 momentum lines in
your copy and confirm the list above, or accept the 2026-10-16 reading. Not relied on:
`Ek = p²/2m` (not recorded as verified), any data-booklet formula.

## Decisions
Each: options, **choice** (recommended), reason. Reversal: edit the decision before the slice
that owns it; after, edit that slice.

- **D1. Division of labour (new in this plan).** (a) Claude writes everything and the guide
  walks the code (the 2.4 precedent); (b) the author writes everything; (c) **Claude writes
  the tests first and everything around the core; the author writes the small pure-physics
  core (13 functions, roughly 80 lines in all), with scaffolding that fades; a fresh
  `reviewer` reviews each author slice and Claude explains each finding**; (d) pair
  programming throughout, Claude typing. (a) and (d) do not teach coding by doing; (b) is
  what the author asked not to have. (c) gives red→green feedback on every function and keeps
  each sitting about 1-2 hours. Rules:
  - **Fading scaffolding**, per sitting: worked example (the guide shows the whole function
    and explains every line; the author types it, not pastes) → fill in the blanks → write
    with hints → write alone. The functions are ordered so each step is small.
  - **Hint ladder** (in the guide, per function): H1 the physics in words; H2 the formula in
    symbols; H3 the code shape with blanks; H4 a near-identical worked example on a different
    quantity. No full solutions in the guide (`docs/CLAUDE.md`: exercises without solutions).
  - **Stuck** (after H4 and about 30 minutes): a pair session in chat. The author drives;
    Claude asks questions and explains. Claude types a core line only when the author asks,
    and never silently replaces the author's code. Every Claude-typed core line is recorded in
    the guide's **authorship ledger** (function, lines, date, why) and named in the commit
    message. Commits all carry the author's identity, so the ledger is the only record.
  - **Tests are fixed**: an author slice changes no test file (`git diff` check in each
    Acceptance block). If a test looks wrong, the author says so; Claude fixes it with a reason.
  - **Review**: the core is scientific core, so each author slice gets 1 fresh `reviewer`;
    findings are explained at IB level and the author makes the fixes (the same ladder).
    Findings and their fixes are recorded in the guide's ledger (one line per finding) and in
    that session's journal entry.
  - **Autopilot**: author slices cannot run on the autopilot; A2 is built in chat sessions.
- **D1b. The author's workflow (the author's answer, 2026-11-21: own laptop, VS Code).**
  The author codes in a local clone in VS Code (Codespaces only as a fallback, one note in
  ch. 1). Per author sitting:
  1. Claude commits the sitting's stubs, tests and chapter to the A2 branch and pushes; this
     is the **test commit** (its hash goes in the journal and the sitting's Acceptance).
  2. The author pulls (VS Code Source Control), edits and saves `core.py` only, runs
     `uv run pytest <file> -q` in the integrated terminal until green, then commits their own
     code (Source Control: stage, message, commit) and pushes to the branch Claude named. The
     laptop clone has no repository hook enabled (`core.hooksPath` is set only in Claude
     sessions), so the author's commits carry **no** Claude co-author trailer: that code is
     the author's, and the missing trailer is part of the authorship record.
  3. Claude fetches, checks the test files are untouched
     (`git diff <test commit> -- <the sitting's test files>` prints nothing), runs the
     Acceptance commands, starts the reviewer and continues.
  Who commits what: the author commits only `core.py` changes of their sitting; Claude
  commits everything else. Environment and tooling errors (install, uv, git, hooks, VS Code)
  Claude fixes at once, outside the authorship ledger, which records only physics-core lines.
- **D2. Where the code lives.** (a) `physics/collisions/`; (b) **`backend/src/simforge/
  physics/foundations/collisions/`**: `core.py` (author, stdlib only), `schemas.py`,
  `model.py` (Claude); route module `api/routes/foundations.py`. (a) would take the name Phase
  4's Track B collision engine needs; (b) keeps Track A visibly separate inside the Physics lab
  (the "Product structure" section). Tests: `backend/tests/physics/foundations/`.
- **D3. Model id, version, endpoint, page.** **`physics.foundations.collisions` v1.0.0**
  (the `physics.` prefix keeps it in the Physics lab's log filter);
  `POST /api/v1/physics/foundations/collisions/simulate`; page
  `/physics/foundations/collisions`. HL is added before the PR, so the version at merge is
  1.0.0.
- **D4. One model or three.** (a) three ids (1-D collision, explosion, 2-D); (b) **one id
  with a request discriminated by `kind`: `collision_1d`, `explosion_1d`, `collision_2d`**
  (precedent: the dataset profile's upload/sample union). (a) triples the registry and 1.6
  wiring (CSV tables, overlay, compare, reopen, stored-fields e2e) for cases that share the
  masses, the core functions and most checks. Each kind keeps a flat, strict schema, so
  `spec()` reads bounds per variant.
- **D5. The `/foundations` index.** (a) wait for A1; (b) **A2 creates it**: a static page
  `frontend/src/app/foundations/page.tsx` listing built modules by subject and syllabus code
  (only A2 now; one sentence pointing to the roadmap for the rest, no "coming soon" cards), a
  "Foundations" nav link and a home-page card. Record at close: the ROADMAP A1 row's "plus a
  `/foundations` index" moves to A2 (a Track A wording change only).
- **D6. SL 1-D and HL 2-D.** (a) SL now, HL in a later module; (b) **both in this step, HL as
  slices S6-S7**, matching the ROADMAP row "1-D SL, 2-D HL". If S6 stalls, the author may
  choose to open the PR with SL only and keep HL as a follow-up (an author decision then).
- **D7. 1-D collision inputs.** m1, m2, u1, u2, e, contact time Δt. Presets: "elastic"
  (e = 1), "perfectly inelastic" (e = 0) are syllabus types; any 0 < e < 1 is "inelastic".
  Body 1 starts on the left; **u1 > u2 is required** (otherwise they never meet): refused with
  a 422 that says so.
- **D8. Explosions.** (a) input the energy released, split by a square root; (b) **input
  the common initial velocity u (default 0, from rest) and fragment 1's final velocity v1;
  output v2 by momentum conservation and the energy released**. (b) is the IB exam shape and
  needs only momentum; (a) needs a square root, so no exact rational tests. Fragment 1 is the
  left one, so **v1 ≤ u is required** (otherwise the fragments would pass through each other;
  refused with a 422). The released energy is **always ≥ 0 (proved)**: with total momentum
  (m1 + m2)u, `KE_after − KE_before = ½m1(v1 − u)² + ½m2(v2 − u)² = ½μ(v1 − v2)²`, a sum of
  squares. So it is computed in that closed form (no cancellation) and compared with the
  kinetic-energy difference as a check; there is no "negative energy" refusal.
- **D9. 2-D HL case.** (a) smooth discs with a contact angle and e along the normal; (b)
  **given u1, u2 and v1 (vectors), find v2 from momentum in each component; report the
  kinetic-energy change and classify it** (lost: inelastic; unchanged within the rounding
  allowance: elastic; gained: needs a stored energy source, flagged). (a) is Phase 4's 2-D
  disc model (Track B) and needs the simultaneous equations the guide does not require; (b)
  is what the guide asks at HL. Visualisation: a momentum vector diagram (p1 + p2 before and
  after, same resultant), not an animation.
- **D10. Force-time graph.** (a) constant force (rectangle); (b) **a half-sine pulse
  `F(t) = (πJ/2Δt)·sin(πt/Δt)` on 0 ≤ t ≤ Δt, drawn with the average-force rectangle `J/Δt`
  dashed**, both areas equal to J. Labelled "pulse shape: a modelling choice; the guide's
  `F = Δp/Δt` gives only the average". (b) shows why the peak force (π/2 × average) matters
  for crumple zones. Claude writes the pulse sampling (it needs sine integration, IB Maths HL
  or later); the author writes `average_force`.
- **D11. Animation.** (a) Plotly animation frames; (b) **a local SVG strip: two carts placed
  from backend-supplied positions (x = v·t, exact, 41 times on −1 ≤ t ≤ 1 s, contact at
  t = 0), with Play/Pause and a time slider; reduced motion shows before and after only**;
  (c) a new animation library (a new dependency: no). (b) keeps physics out of the browser
  and is small. It is not a shared component and pre-empts nothing in 2.6.
- **D12. Syllabus vs extension in the UI.** Badges: "IB syllabus (A.2)" on momentum,
  impulse, average force, collision types, explosions, the 2-D components (HL); "Extension"
  on e and the e-formulas (the "elastic" preset notes that its outcome comes from the
  e-formula with e = 1, an extension; the guide does not require solving it), the
  kinetic-energy-loss formula, the pulse shape, the frame
  (boost) check; "Model identity, not a claim about real collisions" on the Validation
  region (the IB_FOUNDATIONS rule).
- **D13. Learning material.** (a) a Foundations part in `LEARNING_GUIDE.md` only (the
  IB_FOUNDATIONS "Product structure" line); (b) **a separate `docs/FOUNDATIONS_CODING_GUIDE.md`
  (the author's explicit request of 2026-11-21, which overrides that line for coding
  material; recorded in IB_FOUNDATIONS at S8) plus a short physics Part 22 in
  `LEARNING_GUIDE.md` at the close**. Chapters are written one slice ahead (below).
- **D14. Interleaving and time limit.** A2 sits between 2.4 and 2.5 at the author's choice.
  A2 becomes the working branch while it runs, so **Track B (2.5) pauses meanwhile** (one
  chat per branch). Because author sittings set the pace, **the default is to park the A2
  branch three weeks after S0 if it is not merged, and 2.5 proceeds; the author may extend
  once** (or pause A2 earlier). Track B is never delayed indefinitely (preservation rule 3).
  Needs the author's confirmation.
- **D15. Input limits** (Claude, S4; labelled "chosen limits, not physics"): m in
  [0.01, 1000] kg, velocity components in [−100, 100] m/s, e in [0, 1], Δt in
  [1e-4, 10] s; non-finite rejected at the boundary. Mass ratios ≤ 1e5 keep the rounding
  allowance small. **Outputs are bounded** (Newtonian, classroom scale): every final velocity
  component must satisfy |v| ≤ 1000 m/s, else a 422 naming it. For the 1-D collision this
  never triggers: |v| ≤ 3·max(|u1|, |u2|) ≤ 300 m/s (proved: the coefficients of u1 and u2
  in each e-formula have absolute values summing to at most (m1 + 3m2)/(m1 + m2) ≤ 3, and
  symmetrically); explosions and 2-D inputs can exceed it (v2 = ((m1 + m2)u − m1v1)/m2 grows
  with m1/m2), so the cap is tested there.
- **D16. Per-run checks** (Claude, `model.py`, computed with `math.fsum`, independently of
  the core's arithmetic): momentum conserved; centre-of-mass velocity unchanged; restitution
  reproduced (1-D collision); loss by difference agrees with the closed form; impulses equal
  and opposite; pulse area equals `J·(h/2)cot(h/2)` (exact expected value); kinetic energy not
  increased (collision); explosion: released energy by the closed form (≥ 0, proved, D8)
  agrees with the kinetic-energy difference. Kind: exact identity, with a rounding allowance
  `C·ε·scale`, where **scale** is defined per check: momentum `Σ|m·u| + Σ|m·v|`;
  restitution an absolute `ε·max|v|`; kinetic-energy loss or release the total kinetic
  energy before (after, for an explosion from rest); centre of mass `max|v|`. **C comes from
  an operation count** (each rounded product or sum adds at most ε relative; C = 2 × the
  number of rounded operations on the path, stated in a comment) and is then confirmed by
  measurement on the S4 grid (observed). Zero-valued expectations (e.g. total momentum of an
  explosion from rest) are tested exactly in Fraction only.

## The coding guide (`docs/FOUNDATIONS_CODING_GUIDE.md`): structure for the docs builder
IB level, intuition first, short. Every chapter ends with a check of understanding; exercises
have no solutions; the hint ladder sits under each exercise. Excerpts tagged
`<!-- src: path:a-b -->` only for Claude-written code (the author's code changes while
learning; it is excerpted at S8). Each chapter is written before the sitting that needs it.

| Ch. | Content | Written in | Used in |
|---|---|---|---|
| 0 | How to use this guide: sittings, the fading steps, the hint ladder, the stuck rule, the workflow (D1b), the authorship ledger and review log (a table at the end) | S0 | all |
| 1 | Set-up on your laptop: install VS Code, git and uv (uv installs Python); clone the repository; open the folder; the integrated terminal; `cd backend`, `uv sync`; `uv run pytest <file> -q`, dots/F/E; `uv run ruff format`, `uv run ruff check`, `uv run mypy`; Source Control: pull, stage, message, commit, push to the named branch; Codespaces as a fallback (one note) | S0 | S0 on |
| 2 | Variables and numbers: names, `=`, int and float, `+ - * / **`, units in names and comments | S0 | S0 |
| 3 | Functions: `def`, parameters, type hints (`m: float`, `-> float`, why mypy needs them), docstrings | S0 | S0 |
| 4 | `return` (and why `print` is not `return`) | S0 | S0 |
| 5 | Reading a failing test: `assert`, expected vs actual, traceback read from the bottom, red → green | S0 | S0 |
| 6 | `if` and `raise ValueError("...")` for invalid input; `pytest.raises(ValueError, match=...)` | S2 | S2 |
| 7 | Tuples: returning two values, unpacking `v1, v2 = ...`, type `tuple[float, float]` | S2 | S2, S6 |
| 8 | Floats vs exact fractions: `0.1 + 0.2`, `Fraction`, ε, why float tests use `rel_approx`, why the same function runs on both, and **why `0.5 * m * v**2` breaks exactness (0.5 is a float, so a Fraction becomes a float) while `m * v**2 / 2` keeps it** | S2 | S2-S6 |
| 9 | Momentum and kinetic energy: `momentum` (S0), then `kinetic_energy`, `total_momentum`, `total_kinetic_energy`, `centre_of_mass_velocity` | S0 (momentum), S1 | S0, S1 |
| 10 | The 1-D collision: `collide_1d` (perfectly inelastic first, then with e, the extension), its guards | S2 | S2 |
| 11 | Impulse, average force, explosions: `impulse`, `average_force`, `explosion_velocity`, `energy_released` (the sum-of-squares form and why it is never negative) | S3 | S3 |
| 12 | Vectors as tuples (HL): components, `momentum_2d`, `kinetic_energy_2d`, `other_velocity_2d` | S6 | S6 |
| 13 | What Claude built around your code: one request from the page to `core.py` and back (Claude's code, excerpted) | S8 | — |

**Core signatures** (fixed by Claude's stubs in S0; two-body functions take plain arguments,
no lists, so no loops are needed): `momentum(m: float, v: float) -> float`;
`kinetic_energy(m: float, v: float) -> float`; `total_momentum(m1: float, v1: float,
m2: float, v2: float) -> float`; `total_kinetic_energy(m1, v1, m2, v2) -> float`;
`centre_of_mass_velocity(m1, v1, m2, v2) -> float`; `collide_1d(m1, m2, u1, u2, e) ->
tuple[float, float]`; `impulse(m, u, v) -> float` (on that body, `m·(v − u)`);
`average_force(j, dt) -> float`; `explosion_velocity(m1, m2, u, v1) -> float`;
`energy_released(m1, m2, u, v1, v2) -> float`; `momentum_2d(m, v: tuple[float, float]) ->
tuple[float, float]`; `kinetic_energy_2d(m, v) -> float`; `other_velocity_2d(m1, m2, u1, u2,
v1) -> tuple[float, float]` (all parameters `float` unless shown).

## Seams (where tests attach; what each catches and misses)
1. **Core** (`core.py`, author): exact `Fraction` identities and hand-worked examples, float
   cases with `rel_approx`, guards. *Catches* formula, sign and index errors. *Misses* the
   API, limits and display.
2. **Model** (`model.py`, Claude): per-run checks pass on a corner grid; a planted mutant
   (u1 and u2 swapped in v2's formula) fails a check; pulse area; frames. *Catches* assembly
   and threshold errors.
3. **API and registry**: 422s per kind (non-finite, bounds, u1 ≤ u2, v1 > u for an
   explosion, an output above the D15 cap, unknown kind), one golden case per kind, replay,
   contract.
4. **Frontend**: Vitest and Playwright; badges, page, index, animation controls. *Misses*
   science (seams 1-2).

## Slices
Common commands (from `backend/`): `uv run ruff check . && uv run ruff format --check .`,
`uv run mypy`. **"Tests unchanged"** (author sittings) means
`git diff <test commit> -- <the sitting's test files>` prints nothing, where the test commit
is Claude's commit that added them (D1b), not HEAD. Author sittings follow D1b; then a fresh
`reviewer` on the `core.py` diff; the author applies fixes; findings go to the ledger and
the journal. Test conventions for every core test file: guard tests use
`pytest.raises(ValueError, match=...)`; parametrized cases have readable `ids`; where
exactness is tested, the test first asserts `isinstance(result, Fraction)` with the message
"use / 2, not 0.5: a float constant turns the exact Fraction into a float (guide ch. 8)";
zero-valued expectations are tested in Fraction only.

### S0: sitting 0, set-up and the first green test
**Claude (`test-writer-risky` for tests, `builder` for the skeleton and docs):** packages
`physics/foundations/__init__.py` and `collisions/__init__.py`; `core.py` with every stub of
S0-S3 (the signatures above, docstrings with units, `raise NotImplementedError`);
`backend/tests/physics/foundations/__init__.py`; `test_core_momentum.py`; guide ch. 0-5 and
ch. 9's `momentum` part; the A2 branch named in the journal. **Author** (about 1-2 hours,
mostly set-up): install and clone (ch. 1), run the test red, type `momentum` from the worked
example (one line), run it green, commit and push.
**Acceptance.**
- **Test files (new):** `backend/tests/physics/foundations/test_core_momentum.py` (integer
  and half-integer hand examples in floats with `rel_approx`, a negative velocity; no
  Fraction yet).
- **Commands:** `cd backend && uv run pytest tests/physics/foundations/test_core_momentum.py -q`
  (red at the test commit, green at the author's); common commands; the tests-unchanged diff.
- **Checks:** (1) The author's push arrives on the named branch with the author's identity
  (`Mud0709`, the GitHub noreply email) and no Claude co-author trailer? (2) The test was red at the test commit and is green at the
  author's? (3) Tests unchanged, ruff, format, mypy pass? (4) Guide ch. 0-5 exist and
  `python3 scripts/doc_index.py --check` passes?

### S1: sitting 1, energy and totals
**Claude (`test-writer-risky`, docs `builder`):** `test_core_energy.py`; guide ch. 9.
**Author:** `kinetic_energy` (fill in), `total_momentum`, `total_kinetic_energy` (hints),
`centre_of_mass_velocity` (alone).
**Acceptance.**
- **Test files (new):** `backend/tests/physics/foundations/test_core_energy.py` (hand
  examples in floats with `rel_approx`, tolerance justified in a comment; signs; no Fraction,
  which starts in S2 after ch. 8).
- **Commands:** `cd backend && uv run pytest tests/physics/foundations -q`; common commands;
  the tests-unchanged diff.
- **Checks:** (1) The tests fail on the stubs and pass on the author's code? (2) The four
  functions are the author's (the ledger lists any Claude-typed line), ruff, format and mypy
  pass? (3) Tests unchanged? (4) Reviewer findings recorded and every must-fix fixed by the
  author?

### S2: sitting 2, the 1-D collision
**Claude (`test-writer-risky`, docs `builder`):** tests; guide ch. 6-8, 10. **Author:**
`collide_1d`: first the e = 0 case from momentum alone (syllabus), then the general e
formula (extension), then guards (`ValueError` for m ≤ 0, e outside [0, 1], u1 ≤ u2). If
the S1 `kinetic_energy` used `0.5`, the Fraction tests here fail with the ch. 8 message and
the author changes it to `/ 2` (expected, part of the lesson).
**Acceptance.**
- **Test files (new):** `backend/tests/physics/foundations/test_core_collision_1d.py`: the
  three hand examples; Fraction cases (a fixed grid of masses, velocities and
  e ∈ {0, 1/4, 1/2, 1}) for momentum, `v2 − v1 = −e(u2 − u1)`, the loss formula and the
  boost, plus `kinetic_energy` and the totals on Fractions (the `isinstance` assertion);
  floats with `rel_approx` (tolerance justified); `pytest.raises(..., match=...)` per guard.
- **Commands:** `cd backend && uv run pytest tests/physics/foundations -q`; common commands;
  the tests-unchanged diff.
- **Checks:** (1) Every identity holds exactly in Fraction, with no tolerance? (2) e = 1 with
  equal masses swaps the velocities and e = 0 gives a common velocity? (3) Each invalid input
  raises `ValueError` with a message naming the input? (4) Tests unchanged, ruff, mypy pass,
  ledger updated? (5) Reviewer must-fixes fixed by the author?

### S3: sitting 3, impulse, average force, explosions
**Claude (`test-writer-risky`, docs `builder`):** tests; guide ch. 11. **Author:**
`impulse`, `average_force` (guard dt > 0), `explosion_velocity` (v2 by momentum; guard
v1 ≤ u), `energy_released` (the sum-of-squares form `½m1(v1 − u)² + ½m2(v2 − u)²`).
**Acceptance.**
- **Test files (new):** `backend/tests/physics/foundations/test_core_impulse.py`: on the
  m = (1, 3), e = 1, (4, 0) → (−2, 2) example, **`impulse(1, 4, −2) == −6` and
  `impulse(3, 0, 2) == 6` exactly** (a signed value, which catches `m·(u − v)`); impulses
  equal and opposite on the S2 grid (Fraction); `F = J/Δt`; the explosion example
  (v2 = 1, 6 J); zero total momentum from rest (Fraction); released energy 0 when v1 = u;
  released energy equals the kinetic-energy difference exactly in Fraction; guards.
- **Commands:** `cd backend && uv run pytest tests/physics/foundations -q`; common commands;
  the tests-unchanged diff.
- **Checks:** (1) All four core test files pass? (2) The signed impulses are −6 and +6
  exactly? (3) The explosion conserves momentum exactly and reports 6 J, and the
  sum-of-squares form equals the energy difference in Fraction? (4) Tests unchanged, ruff,
  mypy, ledger, reviewer must-fixes done?

### S4: the 1-D model and its API (Claude, risky: `test-writer-risky`, `builder-risky`, `reviewer`, `/security-review`)
`schemas.py` (kinds `collision_1d`, `explosion_1d`; D15 limits; non-finite rejected; u1 > u2
and v1 ≤ u by validators), `model.py` (`MODEL_INFO`, `UNITS`, `ASSUMPTIONS`, D16 checks,
the D15 output cap, pulse curve D10, frames D11; calls the author's core),
`api/routes/foundations.py` with its `ModelEntry`, `api/registry.py`, `api/outputs.py`
union, one golden case per kind appended and pinned with
`cd backend && uv run python -m tests.api.pin_golden_runs`, `make api-types`, SV section
`physics.foundations.collisions` v1.0.0 (identities and the D8, D15 bounds proved, tests
listed, C from the operation count and its measurement labelled observed).
**Acceptance.**
- **Test files:** new `backend/tests/physics/foundations/test_collisions_model.py` (corner
  grid: mass ratio 1e5 both ways, e = 0 and 1, velocities at ±100, explosion from rest and
  moving; the planted mutant fails a check; pulse area equals the exact trapezoid value
  within a few ε; frames continuous at t = 0 with slopes u before, v after; the 1-D collision
  never exceeds 3·max|u|); new `backend/tests/api/test_foundations_collisions_api.py` (a 422
  for NaN, ±Infinity, each bound, u1 ≤ u2, v1 > u, an explosion output above 1000 m/s, an
  unknown `kind`); appended cases (`collision_1d`, `explosion_1d`) in
  `backend/tests/api/test_registry.py`; `backend/tests/api/golden_runs.json`.
- **Commands:** `cd backend && uv run pytest tests/physics/foundations
  tests/api/test_foundations_collisions_api.py tests/api/test_registry.py
  tests/api/test_golden_digests.py -q`; `scripts/run_logged.sh a2-s4 'cd backend && uv run
  pytest -q'`; common commands; `git diff --numstat -- backend/tests/api/golden_runs.json`
  (deletions column 0); `make api-types`, then `git diff --stat frontend/src/lib/api`.
- **Checks:** (1) Every check passes on the corner grid and the mutant fails one? (2) Each
  refusal is a 422 naming the input, and none reaches the core? (3) `golden_runs.json` only
  gains lines and existing digests are unchanged? (4) Full pytest, ruff, mypy pass and the
  regenerated contract is committed? (5) `core.py` unchanged by this slice?

### S5: the SL page, `/foundations` index and animation (Claude, routine: `test-writer`, `builder`)
`frontend/src/app/foundations/page.tsx`, `frontend/src/app/physics/foundations/collisions/
page.tsx`, `components/FoundationsCollisionsLab.tsx` (Workspace; kind selector; presets;
`spec()` fields), momentum bars and kinetic-energy bars (Plotly), force-time graph with the
average rectangle, the SVG animation strip, D12 badges; nav link, home card, 1.6 wiring
(`models.ts`, `tables.ts`, `overlay.ts`, `compare.ts`, `lib/runs/pages.ts`).
**Acceptance.**
- **Test files:** new `frontend/src/components/FoundationsCollisionsLab.test.tsx`, new
  `frontend/e2e/foundations-collisions.spec.ts`; updated `frontend/src/lib/runs/pages.test.ts`,
  `frontend/e2e/stored-fields.spec.ts`.
- **Commands:** from `frontend/`: `npx vitest run src/components/FoundationsCollisionsLab.test.tsx
  src/lib/runs/pages.test.ts`, `npm run lint`, `npm run format:check`, `npm run typecheck`;
  from the root: `scripts/run_logged.sh a2-s5 'scripts/check.sh --e2e'`.
- **Checks:** (1) `/foundations` lists A2 with its syllabus code and links to the page? (2)
  The default run shows equal momentum totals before and after, a smaller kinetic-energy
  total for e < 1, and the force-time graph? (3) e and the pulse shape carry the "Extension" /
  "modelling choice" badges, and Play/Pause and the slider move the carts? (4) A run saves,
  reopens and passes the stored-fields case? (5) `check.sh --e2e` passes?

### S6: sitting 4 (HL), 2-D momentum
**Claude (`test-writer-risky`, docs `builder`):** stubs and tests; guide ch. 12.
**Author:** `momentum_2d(m, v)`,
`kinetic_energy_2d(m, v)`, `other_velocity_2d(m1, m2, u1, u2, v1)` (vectors as
`tuple[float, float]`).
**Acceptance.**
- **Test files (new):** `backend/tests/physics/foundations/test_core_2d.py`: the 90° equal-mass
  example; Fraction cases for momentum in each component; a 1-D explosion case (y = 0 and
  **u1 = u2 = (u, 0)**, so the inputs mean the same thing) agreeing with S3's
  `explosion_velocity`; a rotation check (rotating every vector by a right angle,
  (x, y) → (−y, x), rotates v2 the same way, exactly).
- **Commands:** `cd backend && uv run pytest tests/physics/foundations -q`; common commands;
  tests-unchanged diff.
- **Checks:** (1) The example gives v2 = (2, −2) and equal kinetic energies exactly? (2) Both
  components conserved exactly in Fraction, and the rotation check holds? (3) Tests
  unchanged, ruff, mypy, ledger? (4) Reviewer must-fixes done by the author?

### S7: the HL 2-D case, API and view (Claude, risky API: `test-writer-risky`, `builder-risky`, `reviewer`)
Kind `collision_2d` in the schema; checks (momentum per component, energy classification
with the D16 allowance); the D15 output cap; the vector diagram; an HL badge; a
`collision_2d` golden case appended and pinned with
`cd backend && uv run python -m tests.api.pin_golden_runs`; SV.
**Acceptance.**
- **Test files:** updated `test_collisions_model.py` and `test_foundations_collisions_api.py`
  (2-D grid, KE-gained flagged not hidden, 422s); appended registry case; updated
  `FoundationsCollisionsLab.test.tsx` and `foundations-collisions.spec.ts`.
- **Commands:** the S4 backend commands; `make api-types`; the S5 frontend commands;
  `scripts/run_logged.sh a2-s7 'scripts/check.sh --e2e'`.
- **Checks:** (1) A gained-energy input is flagged "needs a stored energy source", and the
  90° example is classified elastic? (2) `golden_runs.json` only gains lines
  (`git diff --numstat` deletions 0) and earlier digests are unchanged? (3) The
  HL view shows p1 + p2 before and after with the same resultant? (4) `check.sh --e2e` passes
  and `core.py` is unchanged by this slice?

### S8: physics guide part, docs and close-out (Claude, routine: `builder`)
`LEARNING_GUIDE.md` Part 22 (≤ 250 lines: momentum vs energy, impulse and crumple zones,
where the lost energy goes, the frame check; checkpoints and exercises without solutions);
coding guide ch. 13 and excerpts of the author's final code; `IB_FOUNDATIONS.md` (P3 built,
the D13 override, the D5 index note); `ROADMAP.md` A2 ✅ and the A1 wording; `ARCHITECTURE.md`
decision 22 and layout; `README.md` endpoint; `docs/briefs/A2.md`; `docs/HANDOFF.md`; this
plan's status. Then the whole-step `reviewer`.
**Acceptance.**
- **Commands:** `python3 scripts/doc_index.py`, `python3 scripts/doc_index.py --check`,
  `python3 scripts/check_excerpts.py`, `scripts/run_logged.sh a2-close 'scripts/check.sh --e2e'`.
- **Checks:** (1) `check.sh --e2e` passes in full? (2) Every excerpt matches the code? (3)
  `git diff <base> -- ROADMAP.md` (base: the commit before S0) shows hunks only after the
  "## Track A: IB Foundations (ADDITIVE)" heading, so no Track B row or order changed, and
  A2 is ✅? (4) The brief labels every claim proved, tested or observed, and
  the ledger is complete?

## Risks
- **Pace.** Author sittings may run long; D14's parking default protects Track B. Claude never
  speeds up by writing core code unrecorded.
- **Frustration on early red tests.** Mitigated by the fading steps and the hint ladder;
  ruff format removes style friction; mypy errors explained in ch. 3.
- **Tests that over-specify** (e.g. demanding one arithmetic order) would fail correct author
  code: Fraction tests are order-independent; float tests use justified relative tolerances.
- **Cancellation near e = 1:** the loss is shown from the closed form, the difference only
  as a check (Before deciding 1a).
- **Rounding allowance:** C comes from an operation count and is confirmed by measurement
  in S4; until then it is unverified.
- **Local set-up** (the author's laptop): install or PATH problems; Claude fixes them at once
  (D1b), with Codespaces as the fallback.
- **Scope creep into Phase 4 or 2.6:** D9 and D11 keep disc geometry and generic animation out.
- **Syllabus mapping** not re-checked against the guide in this session (see above).

## Out of scope / Not done
Smooth-disc 2-D collisions with a contact angle and e along the normal (Phase 4); multi-body
or sequential collisions; friction during contact; variable mass (rockets); `Ek = p²/2m`
(unverified as syllabus); "Explain" or "Check yourself" panels (added only if the page needs
one, per IB_FOUNDATIONS); a shared animation component (2.6).

## Needs the author's confirmation
1. **Division of labour (D1, D1b):** you write the 13 core functions (about 80 lines) in five
   sittings (S0 set-up, S1-S3, S6) on your laptop in VS Code and commit them yourself; Claude
   writes the tests first and everything else, and records any core line it types.
2. **A2 before 2.5 (D14):** A2 becomes the working branch, so Track B (2.5) pauses while it
   runs; by default the A2 branch is parked three weeks after S0 if it is not merged, and 2.5
   proceeds; you may extend that once.
3. **SL and HL in one PR (D6).**
4. **The A.2 syllabus lines** listed under "Syllabus re-check", re-checked against your copy of
   the Physics guide (first assessment 2025).

## Genuine stops found
None. Checked: no new dependency; no Track B item changed, reordered or dropped (2.5 stays
next in Track B; Phase 4 and 2.6 unchanged); no storage, network or auth change; no guard-rail
path edited; every scientific claim has an exact or closed-form reference. Flagged, not
blocking: the IB_FOUNDATIONS "learning material in the lab guides" line is overridden for
coding material by the author's request (D13).
