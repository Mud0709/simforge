Last updated: deb170f 2026-11-02
<!-- Overwrite after each meaningful task (skill simforge-status). Keep these headings: the
start hook prints "Next action" and "Open decisions". Sha = latest commit described here. -->

# SimForge handoff

## Next action
Review and merge PR #15 (handoff system) once CI is green; you merge it.
Then approve the autopilot fresh-session proposal (shown in chat 2026-11-02; not applied).

## Open decisions
- Autopilot: fresh session per run, approved 2026-11-02; the exact scheduled-task change awaits your OK (proposal in chat). Weekly cap 0.76 (test) or back to 0.70?
- Roadmap: "best angle against drag strength" and "drag-law comparison" are in the capability map but no Phase 2 step (recommend: schedule them; nothing built).
- Deployment risk: no rate limit or concurrency cap on sweeps (~11 s each); matters only if SimForge is ever public.
- Replay: should differing step counts be informational rather than "differs"?
- Not blocking: five optional clean-ups from the 2.1 review (PR #13 description).

## Last task: handoff system and lighter workflow
- **Completed:** start-hook brief; `CLAUDE.md` working style and 5-part report; status and
  autopilot skills read the handoff instead of the conversation; open decisions moved here
  from STATE; your rules of 2026-11-02 (guide chapters ~250 lines; risky-slice + per-PR
  reviews); learning-log entries for 1.6, 2.1, 2.2; one skippable checkpoint question per
  task report; a failed cloud install keeps the brief (exit 0, failure as its last line).
- **Files:** `.claude/hooks/session-start.sh`, `.claude/settings.json`, `CLAUDE.md`,
  `.claude/skills/{simforge-status,autopilot}/SKILL.md`, `.claude/autopilot/STATE.md`,
  `docs/LEARNING_LOG.md`, `docs/HANDOFF.md`. No code, tests, roadmap or science docs.
- **Checks run:** `bash -n` and shellcheck 0.11.0 on the hook (exit 0); the hook run locally
  (0.03 s, exit 0, 7 lines without a handoff); edge cases in a scratch copy (stale, unknown
  or absent sha, missing file or section, CRLF, long sections capped at 20 lines, detached
  HEAD, no origin/main, failing installs in cloud mode); one fresh-context review, findings
  fixed in `3508014`; failing cloud install re-tested after `deb170f` (brief kept, exit 0).
  Not run: `scripts/check.sh` (no code changed); CI on PR #15 not yet checked.
- **State:** committed and pushed (`77b59b9` … `deb170f`, then this file); PR #15 open, not
  merged. Autopilot paused (`waiting-review`, task disabled).
- **Known limits:** the brief shows `origin/main` as last fetched.

## Learning handoff
- **What it does:** each session starts with a short, git-computed brief, and each task ends
  by rewriting this file, so progress survives without the old conversation.
- **Why it matters:** re-reading long chats was the biggest token cost; one short file is
  cheap to read, and you can read and edit it yourself.
- **Key concept:** a single source of truth: each fact lives in one place (git for commits,
  this file for decisions), and everything else links to it.
- **Trade-off:** the handoff is only as fresh as its last update; the sha line and the
  "more than 3 commits" warning make staleness visible instead of silent.
- **You should be able to explain:** why the hook computes facts from git instead of storing
  them, and what the brief does when this file is missing or stale.
