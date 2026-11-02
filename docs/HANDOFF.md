Last updated: 751e243 2026-11-02
Working branch: claude/laughing-brahmagupta-50jkiy
<!-- Overwrite after each meaningful task (skill simforge-status). Keep these headings: the
start hook prints "Next action" and "Open decisions"; the fresh-session autopilot reads
"Working branch" from this file on main. Mark an open decision "(blocks: <unit>)" only if
it stops that unit; answer one by adding a line starting "Answer:" under it. -->

# SimForge handoff

## Next action
Merge PR #16 (you merge). Then say "resume autopilot" (sets status running, resets the work
limit), then one watched test run; the 4-hour schedule only after that.

## Open decisions
- Autopilot: weekly cap 0.76 (test) or back to 0.70? (until answered, STATE's 0.76 applies)
- Roadmap: "best angle against drag strength" and "drag-law comparison" are in the capability map but no Phase 2 step (recommend: schedule them; nothing built).
- Deployment risk: no rate limit or concurrency cap on sweeps (~11 s each); matters only if SimForge is ever public.
- Replay: should differing step counts be informational rather than "differs"?
- Not blocking: five optional clean-ups from the 2.1 review (PR #13 description).

## Last task: autopilot in a fresh session per run
- **Completed:** each run starts a fresh session (Sonnet 5.5) that reads only the brief, this
  file, git and the last journal entry; branch from the line above on `main`; an
  `Autopilot-run` commit trailer tells its writes from yours; explicit `Answer:` lines;
  work limit counts only working-run commits; only `(blocks: …)` decisions stop a run, and
  the stop pauses the task; skipped runs change no files; Opus subagents for high-effort
  work, Sonnet for the rest, recorded in the journal.
- **Files:** `.claude/skills/autopilot/SKILL.md`, `.claude/skills/simforge-status/SKILL.md`,
  `.claude/autopilot/STATE.md`, `CLAUDE.md` (Autopilot paragraph), `docs/HANDOFF.md`.
- **Scheduled tasks:** new `trig_01LWbTdfvYfXswNkcewkKTUU` (fresh session, model
  `claude-sonnet-5-5` confirmed in its config, **no schedule**; prompt matches the skill).
  Old `trig_01D81BmGR4kh1SUbMrdbJi4F` disabled, kept.
- **Checks run:** one fresh-context review (11 findings, fixed in `751e243`); `CLAUDE.md`
  115 lines with Two tracks, Standards, Git and Checks unchanged; hook runs, exit 0. Not
  run: `scripts/check.sh` (no code changed); CI on PR #16 not yet checked.
- **State:** committed and pushed (`c3076d1`, merge `2842566`, `a7b8024`, `751e243`, then
  this file); PR #16 open, not merged. Autopilot `waiting-review`, no schedule.
- **Unverified until the test run:** `add_repo` and pushing to the working branch, GitHub
  tools (the task holds no connectors), a usage reading (`get_session`, `list_events`),
  `PushNotification` and `update_trigger` in a fresh session.

## Learning handoff
- **What it does:** every autopilot run starts with an empty memory and rebuilds its picture
  from files and git, so its cost per run stays flat instead of growing.
- **Why it matters:** the old autopilot re-read an ever-longer conversation each time; now
  what it knows is exactly what you can read in this file.
- **Key concept:** provenance: a fresh run can only trust what it can trace, so its own
  commits carry a marker and only unmarked, explicit edits count as your answers.
- **Trade-off:** state that used to live in memory (who wrote what, whether a push was sent)
  must now be written down or computed from the clock, which adds rules.
- **You should be able to explain:** why the run reads the branch name from `main`, and why
  a commit trailer is needed when every commit has the same author name.
