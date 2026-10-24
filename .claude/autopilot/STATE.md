# Autopilot state

Read and updated by every autopilot tick (`.claude/skills/autopilot/SKILL.md`). The author can
edit it too: change `status` to `paused`, or answer a question under "Waiting for you".

status: running
session: session_01KiMGHphJdZSjdXKDzmfkvm
scheduled task: SimForge autopilot, id trig_01D81BmGR4kh1SUbMrdbJi4F (every 6 hours, UTC)
failures: none
branch: claude/laughing-brahmagupta-50jkiy

## Budget (the author may edit these numbers)
- weekly cap: 0.70. A tick never starts if it would take the 7-day window above this. The
  other 30% is kept for the author.
- weekly cap near reset: 0.90. Applies when the 7-day window resets within 12 hours (what is
  left at the reset is lost anyway).
- five-hour cap: 0.50. Above this, the author is probably working: skip.
- starting estimate of a tick's cost: 0.03 of the 7-day window. Replaced by the largest of
  the last three measurements once there are three.

## Measured tick costs (7-day utilisation before → after)
None yet. For scale: on 2026-10-24 a short reply in this session moved the 7-day window by
about 0.01, because the conversation is long.

## Current unit
None. The next roadmap step is 1.6 (comparison and export). PR #11 (roadmap 1.5) is not
merged yet, so until it is, the autopilot only plans 1.6 (proposals in the journal, no code).

## Remainder of the current unit
—

## Waiting for you (blocking)
Nothing.

## For your daily review (not blocking)
- Learning-log drafts for PRs #9 and #10 (in chat on 2026-10-23): approve or edit.
- PR #11 (roadmap 1.5) is green and waiting for your review and merge. The autopilot's commits
  land on the same branch, so they appear in #11 until it is merged.
