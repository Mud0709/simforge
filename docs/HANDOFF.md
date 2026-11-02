Last updated: 037df73 2026-11-02
Working branch: claude/laughing-brahmagupta-50jkiy
<!-- Overwrite after each meaningful task (skill simforge-status). Keep these headings: the
start hook prints "Next action" and "Open decisions"; the fresh-session autopilot reads
"Working branch" from this file on main. Mark an open decision "(blocks: <unit>)" only if
it stops that unit; answer one by adding a line starting "Answer:" under it. -->

# SimForge handoff

## Next action
Read `docs/plans/ROADMAP_2_3_PLAN.md` (first open decision). The autopilot runs daily at
02:59 UTC and waits on that decision before building slice 1.

## Open decisions
- 2.3 plan unverified by content (blocks: 2.3 slice 1): the planner (Opus) wrote D1-D17; the run checked only its structure. Read it, or ask for a content review; then add `Answer: plan accepted` (or your changes) here.
- Open a PR for the working branch when you want CI on it (autopilot runs may open one; only you merge). CI runs only on PRs and pushes to `main`. Not blocking.
- Branch rules: GitHub offers branch protection on public repositories for personal accounts too (this repo is public), if you want "PRs required" on `main` later. Not blocking.
- Autopilot: weekly cap 0.76 (test) or back to 0.70? Used only when a run can read usage (rarely).
- Roadmap: "best angle against drag strength" and "drag-law comparison" are in the capability map but no Phase 2 step (recommend: schedule them; nothing built).
- Deployment risk: no rate limit or concurrency cap on sweeps (~11 s each); matters only if SimForge is ever public.
- Replay: should differing step counts be informational rather than "differs"?
- Not blocking: five optional clean-ups from the 2.1 review (PR #13 description).

## Last task: autopilot made live and made "genuine"
- **Third test run** (2026-11-02 12:38 UTC, session `cse_01DMcXP2cESzL5QMkKFotK4s`, $2.71):
  repository present, working branch checked out and **pushed** (`037df73`, trailer
  `Autopilot-run: work`), cap counted (1 of 1), CI read: "not run (no PR)", GitHub
  `list_pull_requests` worked, planner on Opus high. Weak spots: plan checked by structure
  only; handoff only partly rewritten.
- **Changed after it:** model and effort from a fixed table by unit type (Opus for plans,
  scientific core, inputs/limits and unclear failures; Sonnet for routine slices and clear
  fixes; unsure → Opus); one escalation to Opus after two failed checks; at most one worker
  and one reviewer per run; content verification journaled under "Verified:"; one push per
  run; schedule wording now daily.
- **Scheduled task** `trig_01LWbTdfvYfXswNkcewkKTUU`: daily `59 2 * * *` (02:59 UTC, 18:59
  Pacific), switched on; auto-fix off (author); never-merge in its prompt.
- **Files:** `.claude/skills/autopilot/SKILL.md`, `.claude/autopilot/STATE.md`, this file.
- **Checks run:** the run's push and trailer confirmed with `git log`; skill lines checked for
  length. Not run: `scripts/check.sh` (no code changed). CI: not run (no PR).
- **State:** committed and pushed to the working branch; no PR open; `main` unchanged since
  PR #16 (`3908bac`).

## Learning handoff
- **What it does:** the autopilot runs once a day in a fresh session, picks its model from a
  fixed table, and must check the content of what it builds before committing.
- **Why it matters:** a rule only works if it is enforced; the schedule enforces the daily
  limit, and the "Verified:" line makes checking visible instead of assumed.
- **Key concept:** separation of duties: the cheaper model coordinates and checks, the
  stronger model does the hard thinking, and neither marks its own work as verified.
- **Trade-off:** the "unverified blocks the next unit" rule can stall progress until you read
  a plan, in exchange for never building on something nobody checked.
- **You should be able to explain:** why Sonnet checking Opus's plan "by structure" is not a
  real check, and what the run now has to check instead.
