Last updated: (this commit) 2026-11-13
Working branch: claude/context-gtqp03
<!-- Overwrite after each meaningful task (skill simforge-status). Keep these headings: the
start hook prints "Next action" and "Open decisions"; the fresh-session autopilot reads
"Working branch" from this file on main. Mark an open decision "(blocks: <unit>)" only if
it stops that unit; answer one by adding a line starting "Answer:" under it. A chat on any
other branch is warned by the start brief and shown this file from origin/<working branch>. -->

# SimForge handoff

## Next action
Open a fresh session and run `/context`; compare with 71.6k (headless measurement says ~35k).
Then review the draft PR for this branch (you merge). Then 2.3 slice 2 (first unit: add the
Acceptance block). Autopilot paused: say "resume autopilot" when ready.

## Open decisions
- Ladder retries now run in the main session (your rule). The scheduled run is Sonnet 5.5, so a failed `high` unit no longer gets an Opus retry, and the run now writes fixes itself (an exception to "the run never writes production code"). Keep, or let rung 3 resume the builder on Opus via `SendMessage`? Recommend: keep, review after two ticks.
- Denied tools are gone from every session in this repo, including `read_documentation`, `get_environment`, `create_trigger` and Claude Docs / Drive / Hugging Face / Coursera. Un-deny one in `.claude/settings.json` when needed.
- Ruleset on `main`: "Require status checks" has no checks selected. Add `Backend (ruff, mypy, pytest)`, `Frontend (eslint, prettier, tsc, vitest, build)`, `API contract in sync`, `End-to-end (Playwright)`. Not blocking.
- Branch clean-up (your clicks): delete `backup/main-before-rewrite`, `backup/branch-before-rewrite` and `claude/epic-sagan-30vpv3`. Not blocking.
- Autopilot: weekly cap 0.76 (test) or back to 0.70? Used only when a run can read usage (rarely).
- Roadmap: "best angle against drag strength" and "drag-law comparison" are in the capability map but no Phase 2 step (recommend: schedule them; nothing built).
- Deployment risk: no rate limit or concurrency cap on sweeps (~11 s each); matters only if SimForge is ever public.
- Replay: should differing step counts be informational rather than "differs"?
- Not blocking: five optional clean-ups from the 2.1 review (PR #13 description).

## Last task: lean start-up context (author's request, 2026-11-13)
- **Completed:** `.claude/settings.json` denies 27 unused `claude-code-remote` tools, the
  Claude Docs, Coursera, Google Drive and Hugging Face servers, `Artifact`, `SearchPlugins`,
  `SuggestPluginInstall`; adds `disableClaudeAiConnectors`. Kept: `get_session`, `list_events`,
  `get_trigger`, `list_triggers`, `update_trigger`, `send_later`, `send_message`,
  `subscribe/unsubscribe_pr_activity`, GitHub MCP. New `.claude/agents/` planner, reviewer
  (read-only), test-writer, builder; the autopilot skill calls them by name, one reviewer per
  tick (three for a scientific-core plan), retries in the main session, grep-then-`sed -n` rule.
- **Measured (headless `claude -p`, same session MCP config, question "Reply with exactly OK"):**
  main session first request 72,244 → 35,290 tokens; default subagent 60,866 → 24,268 (×3, identical);
  `reviewer` agent 7,568 (×3). Graphify harness not found in the repo; this replaces it.
- **Note:** in cloud sessions connectors arrive via `--mcp-config`, so `disableClaudeAiConnectors`
  alone does not remove them; the server-level deny rules do.
- **Checks run:** JSON valid; deny rules hot-reloaded in this session (tools disappeared);
  `doc_index.py --check`. Not run: `check.sh --e2e` (no code changed).
- **State:** committed, pushed, draft PR open; not merged.

## Learning handoff
- **What it does:** every tool's description is sent with every request; denying unused tools
  and giving subagents a short tool list shrinks that fixed cost.
- **Key concept:** fixed vs per-task cost: start-up tokens are paid by every session and subagent.
- **Trade-off:** a denied tool is unavailable until someone un-denies it.
