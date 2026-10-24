# Autopilot journal

One entry per autopilot tick that did something, newest first. Each lists what was done, the
checks that actually ran, decisions taken without you (with how to reverse them), anything
waiting for you, and the next step. Protocol: `.claude/skills/autopilot/SKILL.md`; current
state: `.claude/autopilot/STATE.md`.

---

## 2026-10-24 12:27 UTC: paused; usage-aware ticks every 6 hours (author's request)
- **Did:** paused the autopilot (scheduled task disabled, STATE `paused`). Changed the schedule
  to every 6 hours. Added a budget gate: each tick reads the author's live 5-hour and 7-day
  usage from this session's events and skips unless it fits under the caps in STATE (7-day
  ≤ 70%, or 90% within 12 h of the weekly reset; 5-hour < 50%). Work is delegated to a
  subagent at an effort level chosen for the job (low, medium or high; never above high).
- **Usage:** 7-day 72%, 5-hour 19% at 12:24 UTC. The 7-day window resets 2026-10-25 02:00 UTC.
- **Checks run:** none needed (no code changed).
- **Decisions taken for you:** the caps (70% / 90% / 50%) and the starting cost estimate (3%
  of the week per tick, replaced by measurements). Edit them in STATE's "Budget" section.
- **Waiting for you:** "resume autopilot" when you want it running; merge PR #11.
- **What this means for you:** the autopilot now spends only the part of your weekly allowance
  you are not likely to use, and it learns what a tick really costs.
- **Learning checkpoint:** why may the autopilot use more of the weekly allowance in the 12
  hours before the reset than earlier in the week?
- **Next:** on resume, plan roadmap 1.6 as proposals (no code until PR #11 is merged).

## 2026-10-24 12:20 UTC: autopilot set up (by the author's request, not a tick)
- **Did:** wrote the protocol (`.claude/skills/autopilot/SKILL.md`), this journal and STATE;
  an independent review found 10 weaknesses, all fixed before switching on; created the
  scheduled task "SimForge autopilot" (every 2 hours, into this session).
- **Checks run:** none needed (no code changed).
- **Decisions taken for you:** every 2 hours; a limit of 6 commits without you; your GitHub
  login `Mud0709` is the only source of instructions on GitHub. Change any of these in chat.
- **Waiting for you:** merge PR #11 (green) so 1.6 can start; approve the learning-log drafts
  for PRs #9 and #10.
- **What this means for you:** work continues between your reviews, but nothing merges
  without you, and every decision it took alone is listed here so you can reverse it.
- **Learning checkpoint:** why does the autopilot refuse to start 1.6 on the same PR as 1.5?
- **Next:** plan roadmap 1.6 (comparison and export) as proposals; build once #11 is merged.

