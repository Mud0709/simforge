# Autopilot journal

One entry per autopilot tick that did something, newest first. Each lists what was done, the
checks that actually ran, decisions taken without you (with how to reverse them), anything
waiting for you, and the next step. Protocol: `.claude/skills/autopilot/SKILL.md`; current
state: `.claude/autopilot/STATE.md`.

---

## 2026-10-24 18:40 UTC: new rule, pick up from the latest conversation (author's request)
- **Did:** the skill's reorient step now reads the session's latest exchange (the author's last
  message and the final response) before choosing work, so a tick continues from work the
  author did in chat between ticks instead of from the previous tick. CLAUDE.md notes it.
  The 18:26 tick was skipped (7-day status `allowed_warning`, 77%).
- **Checks run:** none needed (protocol and docs only).
- **Decisions taken for you:** it reads conversation events back to your last message
  (alternative: only STATE; reverse by deleting the paragraph in step 1.1).
- **Waiting for you:** nothing.
- **What this means for you:** you and the autopilot share one thread of work, so working
  between ticks never makes it redo or undo your session.
- **Learning checkpoint:** why is STATE alone not enough for a tick to know where work stands?
- **Next:** roadmap 1.6, slices S1-S5 (in progress in chat).

## 2026-10-24 12:58 UTC: 1.6 decisions answered; resumed (author's request, not a tick)
- **Did:** recorded the author's answers (yes to all 10, tree confirmed) in the plan and
  STATE; status `running`; 6-hourly task re-enabled (next 18:26 UTC). Work-limit count reset.
- **Checks run:** none needed (docs only).
- **Decisions taken for you:** none.
- **Waiting for you:** merge PR #11; the weekly cap is still 0.76 (your test setting).
- **What this means for you:** the design is settled, so ticks after the merge can build.
- **Learning checkpoint:** why does the plan pin the reference run in the URL, not the database?
- **Next:** after the merge, slice 1 (recompute route) with `tdd`, on a new PR.

## 2026-10-24 12:44 UTC: planned roadmap 1.6 as proposals (test tick 2)
- **Did:** wrote `docs/plans/ROADMAP_1_6_PLAN.md`: what 1.6 builds, 8 decisions with
  recommendations, 5 test-first slices, risks. No code (PR #11 is not merged). Autopilot
  commits since your last message: 1 of 6. Status set to `waiting-review` (nothing else can be
  built until you answer) and the 6-hourly task paused, so waiting costs you nothing.
  Answering the decisions in chat resumes it.
- **Usage:** 7-day 0.73 → 0.73 (under 0.01; readings are rounded to 0.01), 5-hour 0.24 at
  start, 0.27 at the end. One subagent, effort high, same model as this session.
- **Checks run:** none needed (docs only). PR #11 CI on its head: all four jobs green. Three
  of the subagent's claims re-checked in the code (series not stored; Solow's "baseline" and
  "scenario" names; replay's 409 on a version change): all true.
- **Decisions taken for you:** the plan lives in a new `docs/plans/` folder (alternative: in
  this journal; reverse by moving it).
- **Waiting for you:** D1-D8 in the plan; merge PR #11.
- **What this means for you:** the biggest choice is D1: series are not stored, so exports
  of old runs must be recomputed, and the output digest proves the recomputation matches.
- **Learning checkpoint:** why can a CSV cell like `=HYPERLINK(...)` be dangerous, and why
  must the fix leave `-3.2` alone?
- **Next:** your answers, then slice 1 (backend recompute) with `tdd`.

## 2026-10-24 12:32 UTC: resumed, with a one-off test tick (author's request, not a tick)
- **Did:** set STATE `running`, re-enabled the 6-hourly task (next run 18:26 UTC), and
  scheduled one extra test tick for about 12:38 UTC. Added a rule to the skill: subagents
  always inherit this session's model (Opus 5.5); only the effort varies (low, medium, high).
  Changing the model is a proposal for the author. Work-limit count reset to 0 of 6.
- **Usage:** 7-day 72%, 5-hour 21% at 12:26 UTC. The weekly cap is 70% until 14:00 UTC (12 h
  before the 02:00 UTC reset), so the test tick is expected to skip under the budget gate.
- **Checks run:** none needed (no code changed).
- **Decisions taken for you:** none.
- **Waiting for you:** merge PR #11; approve the learning-log drafts for PRs #9 and #10.
- **What this means for you:** the test shows the gate working; real work starts on the first
  tick that fits under the cap.
- **Learning checkpoint:** why is a skipped tick still not completely free?
- **Next:** the test tick, then 18:26 UTC: plan roadmap 1.6 as proposals.

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

