Last updated: 8900f0b 2026-11-15
Working branch: claude/laughing-brahmagupta-50jkiy
<!-- Overwrite after each meaningful task (skill simforge-status). Keep these headings: the
start hook prints "Next action" and "Open decisions"; the fresh-session autopilot reads
"Working branch" from this file on main. Mark an open decision "(blocks: <unit>)" only if
it stops that unit; answer one by adding a line starting "Answer:" under it. A chat on any
other branch is warned by the start brief and shown this file from origin/<working branch>. -->

# SimForge handoff

## Next action
Review the draft PR `claude/determined-meitner-xpu871` into the working branch (you merge). Then
open a FRESH session (agent files are read at session start) and run `/context` to compare with
the numbers below. Then 2.3 slice 3 (Acceptance block and the evaluation budget first).

## Open decisions
- Stored scheduled-task prompt (task `trig_01LW…`, disabled) still repeats the 4-subagent cap, the effort ladder and the read rule; I may not change it. Recommend: shorten it to "follow `.claude/skills/autopilot/SKILL.md`; never merge" and keep steps 0, 1 and 4.
- STATE says `status: running` but the scheduled task is disabled (last fired 2026-11-10). Set `paused`, or say "resume autopilot" (re-enables it, resets `work limit from:`).
- `.github/pull_request_template.md` "Reviews" line is a fourth copy of the old risky/review wording; not edited (outside the paths you authorised). Recommend: point it at `CLAUDE.md`.
- `explorer` and `test-runner` (Haiku lookups) do not count toward the 4-subagent cap (my call, skill step 4). Keep?
- `maxEffortLevel: high` blocks `xhigh`/`max` for every session here (the lowest cap wins); to use them, raise that line. Keep as is?
- Ponytail: its saving (about 10% in the one independent test) is unverified here. Recommend: keep for two ticks, then compare journal costs; off-switch is in `.claude/skills/ponytail/SKILL.md`.
- Ruleset on `main`: "Require status checks" has no checks selected (add `Backend (ruff, mypy, pytest)`, `Frontend (eslint, prettier, tsc, vitest, build)`, `API contract in sync`, `End-to-end (Playwright)`). Branch clean-up (your clicks): `backup/main-before-rewrite`, `backup/branch-before-rewrite`, `claude/epic-sagan-30vpv3`. Not blocking.
- Roadmap: "best angle against drag strength" and "drag-law comparison" are in the capability map but no Phase 2 step (recommend: schedule them). 2.4: keep the exact-vs-numerical table beside the new checks (recommended: yes; `docs/plans/ROADMAP_2_4_NOTES.md`).
- Not blocking: sweep rate limit (matters only if public); replay "differs" for step counts; oscillator energy check normalisation; five clean-ups from the 2.1 review (PR #13).

## Last task: model routing, one-place rules, enforcement (author's request, 2026-11-15)
- **Done:** `CLAUDE.md` holds the model table, the one risky definition, the review rule, the read rule, the test-output rule and "Compact instructions" (168 lines). Eight agents pin model and effort in front-matter (Haiku high: `explorer`, `test-runner`; Sonnet medium: `builder`, `test-writer`; Opus medium: `*-risky`, `planner`, `reviewer`); a test keeps them equal to the table. `SKILL.md` 305 to 237 lines: retry ladder by model, live-usage caps removed (daily cap stays 2), stale example fixed. Settings: `effortLevel` medium, `maxEffortLevel` high, `autoCompactWindow` 200000.
- **Enforced (tested in `backend/tests/scripts/test_hooks.py`, `test_agents.py`):** subagents cannot `git commit`, `git push` or `gh pr`; `reviewer`/`explorer` cannot write; a tick's marker file blocks edits to `.claude/hooks/guard-rails.txt` paths and adds the `Autopilot-run:` trailer; the same failing command stops after 3 failures (ported from TokenEconomizer's loop guard; seen working live). `scripts/run_logged.sh` + `tick_metrics.py --summary` keep test output in a log.
- **Verified:** headless sessions that spawned all 8 agents: each ran on its pinned model and effort; only the two builders saw `ponytail`; project-level hooks blocked push and writes inside subagents. Agent-scoped front-matter hooks did NOT fire in headless runs (kept, plus the project-level layer). Backend: ruff, mypy, doc index, excerpts, 2442 tests passed. Not run: frontend and Playwright (no frontend code changed).
- **Not enforceable by script:** the 4-subagent cap, the daily cap, the work limit, the `failures` counter, "bash can't write" for a determined agent (`python -c`), shell writes to guard rails.
- **Start-up context (headless `/context`, same machine):** 19.2k to 20.6k tokens (CLAUDE.md 3.3k to 4.5k, agents 0.26k to 0.42k, ponytail 0.1k); window 1M to 200k. It costs more at start; the savings are per task (Haiku lookups, logs not output, no duplicate rules).
- **State:** committed and pushed to `claude/determined-meitner-xpu871`; draft PR open; not merged. Branch = working branch + `main` (PR #20) merged, since the two had diverged.

## Learning handoff
- **What it does:** each agent's model and effort are written in its own file, and hooks stop an agent doing what its role forbids.
- **Key concept:** a rule in prose is a request; a rule in a hook is a fact. The tests found a real bug (`sed -i` slipped through).
- **Trade-off:** more CLAUDE.md text costs tokens in every session, so each rule lives in one place and the rest point to it.
