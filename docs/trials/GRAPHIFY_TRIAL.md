# Graphify trial: does a code graph cut a session's reading cost?

**Verdict after two rounds: no. Do not adopt.** Round 2 (2026-11-14, below) was designed to be
conclusive: 40 runs, native tools, cost read from the transcripts' token usage, blind grading.
The graph made sessions slightly *more* expensive at the same accuracy.

## Round 2 (2026-11-14): 10 questions × 2 arms × 2 repeats, blind-graded

**Design.** Code: the working branch @ 7a7af47 (229 code files; read-only worktree, so the
running autopilot was untouched). Ten questions covering every kind a session asks: impact
(`input_hash`), constants (oscillator thresholds), a frontend-to-backend trace, test coverage,
an unfamiliar helper (`_on_side`), a same-name trap (two different `vacuum_optimum`s), registry
structure, error flow, a cross-layer type, and "most depended-on modules" (Graphify's home
ground). Rubrics with key points were written before any run (`graphify-round2/rubric.md`).
Each question ran 4 times on Sonnet (the autopilot builder model): with/without the graph, in
two waves. Agents used their normal tools (Read, Grep, Glob, Bash); the graph arm also had the
Graphify CLI and its own usage rule. No hooks, no Graphify text in any CLAUDE.md (the global
one Graphify had written was parked) for either arm. **Cost** = each transcript's summed token
usage weighted at Sonnet's price ratios (input 1, cache write 1.25, cache read 0.1, output 5).
**Accuracy**: one fresh Opus grader marked all 40 answers against the rubric, blind to the arm,
checking doubted claims in the code. Pairs are matched within a wave, so cache effects cancel.

| | Graph | No graph |
|---|---|---|
| Rubric score (blind) | 86.0 / 94 (91.5%) | 85.5 / 94 (91.0%) |
| False claims | **6** | 2 |
| Cost (all 20 runs, input-token equivalents) | 1,551,910 | 1,496,090 (graph **+3.7%**) |
| Cost above each wave's fixed start-up | +13% to +17% | baseline |
| Bytes of tool output read | 252,963 | 174,439 (graph **+45%**) |
| Tool calls | 63 | 59 |

Paired over the 20 matched runs: cost +6.9% per pair (95% bootstrap CI −0.8% to +15.1%; graph
dearer in 13/20); bytes read higher in 15/20 (sign test p = 0.04). Accuracy is a tie.

| Q | Graph: score, errors, cost, bytes | No graph: score, errors, cost, bytes |
|---|---|---|
| 1 impact of `input_hash` | 9/10, 0, 154k, 19 KB | 9/10, 1, 148k, 26 KB |
| 2 oscillator thresholds | 9/10, 1, 171k, 41 KB | 9/10, 0, 197k, 50 KB |
| 3 replay/outputs trace | 10/10, 3, 189k, 35 KB | 10/10, 0, 187k, 30 KB |
| 4 body-limit tests | 7/10, 2, 137k, 10 KB | 8/10, 0, 132k, 10 KB |
| 5 `_on_side` | 8/8, 0, 142k, 55 KB | 8/8, 0, 128k, 8 KB |
| 6 two `vacuum_optimum`s | 10/10, 0, 126k, 17 KB | 9/10, 0, 113k, 7 KB |
| 7 registry map | 10/10, 0, 222k, 32 KB | 10/10, 0, 198k, 23 KB |
| 8 `ModelDomainError` | 7/8, 0, 137k, 21 KB | 8/8, 1, 124k, 9 KB |
| 9 validation checks UI | 8/10, 0, 130k, 17 KB | 6.5/10, 0, 134k, 5 KB |
| 10 most-imported modules | 8/8, 0, 145k, 6 KB | 8/8, 0, 136k, 6 KB |

**Why.** A graph query returns 3-27 KB of nodes around a name (Q5: 27 KB per query, to find a
helper grep finds in 0.3 KB), and the agent still greps and reads the lines afterwards: the
graph adds a step rather than replacing one. Grep is already a precise index on a repo this
size. On "most-imported modules" both graph runs said the query "returned nothing useful" and
counted imports with grep. The graph helped on one question (Q2, −13%) and modestly on Q9's
completeness; neither outweighs the rest. Not tested: repos ten times larger, where it may pay.

Evidence: `docs/trials/graphify-round2/` (rubric, per-run metrics, blind grades, the unblinding
key, the transcript parser).

## Round 1 (2026-11-13): 5 questions, one run each Measured on `main` @ 067c3e7 with graphifyy 0.9.108
(PyPI; repository now `Graphify-Labs/graphify`, author safishamsi), code-only build
(`graphify extract . --code-only`, no model calls), `GRAPHIFY_QUERY_LOG_DISABLE=1`, never `--strict`.

## Method
- Five questions a session here typically asks, each answered twice by a fresh Sonnet subagent
  (the autopilot's builder model): once with the graph, once without. All 10 ran in parallel.
- Both arms used only Bash, through a wrapper that logged every command and the bytes of its
  output (measured, not self-reported). The graph arm got Graphify's own CLAUDE.md rule verbatim
  ("query before your first grep or read") and the binary/graph paths.
- Fairness: during the runs the Graphify hooks and CLAUDE.md section were removed and the graph
  lived outside the repo, so the no-graph arm saw no nudges and could not find it.
- Correctness scored against reference answers worked out by hand before the runs.
- Tokens and tool calls are the harness's per-agent figures. About 65k of each agent's tokens
  are the fixed start-up context (system prompt, CLAUDE.md), the same in both arms.

## Results

| Q | Question | Arm | Tool calls | Files opened | Bytes read | Tokens | Correct |
|---|---|---|---|---|---|---|---|
| 1 | What calls `record_run`, up to the endpoints? | no graph | 7 | 5 | 13,164 | 71,198 | yes |
| 1 | | graph | 7 | 4 | 12,206 | 71,440 | yes |
| 2 | Where are the oscillator's thresholds set and enforced? | no graph | 6 | 1 | 52,689 | 74,712 | yes (missed the ζ < 1/√2 peak rule) |
| 2 | | graph | 5 | 1 | 22,022 | 76,100 | partial (same miss; constants' line numbers wrong by ~14) |
| 3 | What breaks if the `Workspace` layout changes? | no graph | 6 | 6 | 23,389 | 76,872 | yes |
| 3 | | graph | 5 | 2 | 25,232 | 78,384 | yes |
| 4 | Where is the request-body limit enforced and defined? | no graph | 3 | 3 | 8,973 | 68,756 | yes |
| 4 | | graph | 3 | 2 | 12,224 | 70,584 | yes |
| 5 | Trace the quadratic angle-sweep POST to the pure function | no graph | 6 | 3 | 11,766 | 70,707 | yes |
| 5 | | graph | 6 | 3 | 14,024 | 71,920 | yes |
| | **Total** | no graph | 28 | 18 | 109,981 | 362,245 | 5/5 |
| | | graph | 26 | 12 | 85,708 | 368,428 | 4/5 + 1 partial |

## Reading the numbers
- **Bytes read fell 22%, but one outlier carries all of it.** Without the graph, Q2's agent ran
  `cat` on a 52 KB file; that is a habit, not something only a graph fixes (the root CLAUDE.md
  already says to open one section). Without Q2, the graph arm read **11% more** (63.7 KB vs
  57.3 KB): each `graphify query` returns 1-12 KB of nodes, often off-target (e.g. "what calls
  record_run" seeds on every `run()` in the repo), and the agent still had to grep and read.
- **Total tokens were 1.7% higher with the graph.** Tool calls fell by 2 of 28. Within noise.
- **Accuracy was the same or slightly worse.** The one degraded answer (Q2) quoted line numbers
  that disagree with the file.
- **Why little gain here:** the repo is small (220 code files) and well signposted (`docs/INDEX.md`,
  folder CLAUDE.md files, descriptive names), so grep already lands in one or two hops.

## Costs the trial excluded (they would make the graph arm worse)
- The CLAUDE.md section Graphify writes: ~1.2 KB in every session's start-up context.
- The PreToolUse hook nudge (~0.7 KB observed once on a Bash call) on search/read calls.
- The skill file is 50.5 KB (~12.6k tokens) when loaded.
- `graph.json` is 3.1 MB, rewritten whole on every build (plus a 3.9 MB cache): heavy churn if committed.
- The installed hooks hard-code the absolute path of this container's install, so they break in
  any fresh session unless a setup script reinstalls Graphify at the same path.
- Build cost is small: 4 s full, 5 s incremental (`graphify update .`), no model calls.

## Recommendation
Do not adopt it for the autopilot. The cheaper lever is the one Q2 exposed: telling builders to
grep for the symbol and `sed -n` the located range rather than `cat` a whole file. Revisit Graphify
if the repo grows several-fold or cross-file impact questions start costing many hops. If adopted
then, rebuild at session start (5 s, no commit churn) rather than committing `graphify-out/`.
