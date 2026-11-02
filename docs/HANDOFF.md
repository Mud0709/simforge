Last updated: 672d1c2 2026-11-02
Working branch: claude/laughing-brahmagupta-50jkiy
<!-- Overwrite after each meaningful task (skill simforge-status). Keep these headings: the
start hook prints "Next action" and "Open decisions"; the fresh-session autopilot reads
"Working branch" from this file on main. Mark an open decision "(blocks: <unit>)" only if
it stops that unit; answer one by adding a line starting "Answer:" under it. -->

# SimForge handoff

## Next action
Attach the repository to the autopilot's scheduled task on claude.ai (first open decision);
then a third watched test run (planning 2.3); the 4-hour schedule only after it works.

## Open decisions
- Autopilot repository (blocks: every autopilot run): runs start with no repository and cannot attach one (`add_repo` is not callable in them). On claude.ai, edit the scheduled task "SimForge autopilot (fresh session)" and select the repository `Mud0709/simforge` (and the GitHub connector, if offered, which would also let runs open PRs). If GitHub access is missing, reconnect it at https://claude.ai/connect-github.
- GitHub access for autopilot runs: their `gh` token is invalid and they hold no GitHub tools, so they cannot open PRs (CI is still readable: the repo is public). Fix the token, or recreate the task with the GitHub connector. Not blocking.
- CI on the working branch: CI runs only on PRs and pushes to `main`, so autopilot pushes get no CI until a PR is open. Option: add `push` for `claude/**` branches to `.github/workflows/ci.yml` (your call; a guard-rail file). Not blocking.
- Autopilot: weekly cap 0.76 (test) or back to 0.70? Now used only when a run can read usage (rarely).
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
  run: `scripts/check.sh` (no code changed). CI on PR #16: all 4 checks passed.
- **State:** merged in PR #16 (`3908bac`, checks green on `966092c`). Autopilot resumed:
  STATE `running`, `work limit from: 3908bac`; task has no schedule yet.
- **Test runs 2026-11-02** (Sonnet 5.5, no files changed, $0.12 + $0.10): both stopped at
  step 0. The second called `mcp__claude-code-remote__add_repo` directly: not available, so
  the session has no repository (tag `config:no-git-repo`). PushNotification worked;
  `get_session`/`list_events`, GitHub tools and `update_trigger` were not available to it.
  Untested: push, CI read, the budget gate.

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
