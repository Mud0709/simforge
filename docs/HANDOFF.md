Last updated: 040c642 2026-11-08
Working branch: claude/laughing-brahmagupta-50jkiy
<!-- Overwrite after each meaningful task (skill simforge-status). Keep these headings: the
start hook prints "Next action" and "Open decisions"; the fresh-session autopilot reads
"Working branch" from this file on main. Mark an open decision "(blocks: <unit>)" only if
it stops that unit; answer one by adding a line starting "Answer:" under it. A chat on any
other branch is warned by the start brief and shown this file from origin/<working branch>. -->

# SimForge handoff

## Next action
Review the token-saving docs change and the protocol upgrade (this branch; not merged); run
/context in a fresh session to confirm the numbers below. Then 2.3 slice 2 (its first unit:
add the Acceptance block). Autopilot paused: say "resume autopilot" when ready.

## Open decisions
- Ruleset on `main`: "Require status checks" has no checks selected. Add `Backend (ruff, mypy, pytest)`, `Frontend (eslint, prettier, tsc, vitest, build)`, `API contract in sync`, `End-to-end (Playwright)`. Not blocking.
- Branch clean-up (your clicks): delete `backup/main-before-rewrite`, `backup/branch-before-rewrite` and `claude/epic-sagan-30vpv3`. Not blocking.
- Autopilot: weekly cap 0.76 (test) or back to 0.70? Used only when a run can read usage (rarely).
- Roadmap: "best angle against drag strength" and "drag-law comparison" are in the capability map but no Phase 2 step (recommend: schedule them; nothing built).
- Deployment risk: no rate limit or concurrency cap on sweeps (~11 s each); matters only if SimForge is ever public.
- Replay: should differing step counts be informational rather than "differs"?
- Not blocking: five optional clean-ups from the 2.1 review (PR #13 description).

## Last task: docs as a token-saving backend (author-authorised guard-rail edits, 2026-11-08)
- **Completed:** (1) ladder: high-effort units start on Opus, low/medium on Sonnet, retries on
  the same model up to high, then Opus; (2) stored autopilot prompt reads the brief, this file,
  the newest journal entry and the confirmed findings only (task still paused); (3) one
  journal file per tick in `docs/journal/` (template, `Journal.base` table for Obsidian),
  `AUTOPILOT_JOURNAL.md` a closed archive; (4) `scripts/tick_metrics.py` writes test counts,
  durations and pass/fail (from exit codes) into the entry; (5) `scripts/doc_index.py` →
  `docs/INDEX.md` (10 docs, 404 sections), stale index fails `check.sh` and the backend tests;
  (6) folder rules in `backend/`, `frontend/`, `docs/CLAUDE.md` (they load only there; seen
  working); (7) `.obsidian/` ignored. The new scripts, template and folder files are guard rails.
- **Context measured (bytes; tokens ≈ bytes/4, an estimate):** a fresh session's project text
  (root `CLAUDE.md` + start brief) was 10,794 bytes before and 10,826 after: unchanged, since
  the root keeps the rules that apply everywhere. **Not measured: `/context`** (only the author
  can run it). The savings are per task: one guide chapter 26.5 KB instead of the 256 KB guide;
  one journal entry ~1.3 KB instead of the 30 KB archive; folder rules (1.1-1.6 KB each) only
  where the work is.
- **Files:** `scripts/doc_index.py`, `scripts/tick_metrics.py`, `scripts/check.sh`,
  `docs/INDEX.md`, `docs/journal/`, `backend/tests/scripts/`, the four `CLAUDE.md` files,
  `.claude/skills/autopilot/SKILL.md`, `docs/AUTOPILOT_JOURNAL.md`, `.gitignore`, this file.
- **Checks run:** backend ruff, format, mypy, `pytest -q` (2088 passed); the 20 script tests
  (real pytest and Vitest logs, exit codes, failing files, flaky, idempotence); all 404 index
  ranges checked against their headings; `doc_index.py --check`; `bash -n scripts/check.sh`;
  the hook (exit 0). One fresh-context review (Opus): 12 findings, all fixed. Not run: the
  full `scripts/check.sh --e2e` (frontend unchanged). CI: not run (no PR).
- **State:** committed and pushed to the working branch; no PR open; not merged.

## Learning handoff
- **What it does:** sessions load a short map and open one section of a large document by its
  line range; the autopilot's journal is one small file per run whose numbers come from a script.
- **Why it matters:** reading a 256 KB guide to use one chapter costs ten times the tokens;
  numbers a model types can be wrong, numbers a parser reads from tool output cannot drift.
- **Key concept:** an index (a map from topic to location) trades a little upkeep (regenerating
  it, enforced by a check) for much cheaper lookups.
- **Trade-off:** every edit to a large document now also regenerates the index, or CI fails.
- **You should be able to explain:** why the startup context barely changed while per-task
  reading fell by about ten times.
