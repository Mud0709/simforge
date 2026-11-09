# Autopilot findings

One line per lesson about this repository or its tools, written when it cost a tick (or a
session) something: a failed attempt, a wasted subagent, a wrong assumption. Format:
`- [seen N] <lesson> (cost; sightings: <dates>)`, becoming `- [confirmed]` at the third
sighting. The start hook prints the confirmed lines only. Rule: `.claude/skills/autopilot/SKILL.md`
step 4. Seeded on 2026-11-07 from the journal and the sessions so far.

- [confirmed] A fresh-context review finds real defects the builder missed; budget for a fix round (cost: rework units; sightings: 1.6 four bugs 2026-10-24, 2.1 2026-10-27, 2.3 slice 1 three passes 2026-11-03).
- [confirmed] Scheduled fresh sessions have no `get_session`/`list_events`, so they cannot read usage; the budget gate counts runs in git instead (cost: a redesign of the gate; sightings: 2026-11-02 09:27, 2026-11-02 12:29, 2026-11-02 12:50 "usage not read").
- [seen 1] `update_trigger` was missing in one scheduled run (2026-11-02 12:29, no repository attached) but present at 09:27; try it before falling back to a notification (cost: a run that could not pause; sighting: 2026-11-02 12:29).
- [seen 2] The safety check refuses destructive git: use `git switch`, merge commits and `--force-with-lease` only when the author authorises (cost: blocked steps; sightings: force-push 2026-11-02, `git reset --hard` 2026-11-03 02:59).
- [seen 2] Error measured against a scale larger than the motion hides real error; also measure against the motion reached (cost: a reversed decision; sightings: 2.3 slice 1 Q limit, short runs 2026-11-03).
- [seen 1] `pytest.approx` adds abs=1e-12 by default and silently loosens tolerances; use `tests/approx.py` `rel_approx` (cost: 46 weak assertions; sighting: 2026-10-27).
- [seen 1] CI's CPU can differ in the last bit from this machine; write bounds in ulps or eps (cost: a red CI run; sighting: 2.1 2026-10-27).
- [seen 1] ToolSearch by a short name finds nothing in a scheduled run; call tools by their full `mcp__...` names (cost: a wasted test run; sighting: 2026-11-02 09:27).
- [seen 1] Playwright 1.56.1 cannot install Chromium on `ubuntu-latest` (26.04); CI's e2e job is pinned to 24.04 (cost: a red CI run; sighting: 2026-10-27).
- [seen 1] A GitHub ruleset aimed at the working branch blocks every direct push there; rulesets belong on `main` (cost: a refused push; sighting: 2026-11-02).
