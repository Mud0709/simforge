# Docs notes (loaded when work happens in `docs/`)

- **Open large documents by section.** `docs/INDEX.md` lists every Markdown file of 20 KB or
  more (except the closed journal archive and `journal/`) with its sections and line ranges;
  read one range (offset and limit) instead of the whole file. After changing an indexed
  document, run `python3 scripts/doc_index.py`; `scripts/check.sh` and the backend tests fail
  on a stale index.
- **Learning guides** (`LEARNING_GUIDE.md`, `ECONOMY_LEARNING_GUIDE.md`,
  `QUANT_LEARNING_GUIDE.md`): every task adds or updates its chapter, with checkpoints and
  exercises without solutions. New chapters stay at about 250 lines with few verbatim excerpts
  (the author's rule of 2026-11-02): the science stays complete, the prose is not exhaustive.
  Excerpts are tagged `<!-- src: path:a-b -->` and must match the files exactly; update the
  line references when code moves (`python3 scripts/check_excerpts.py`; `scripts/check.sh` and the
  backend tests fail on a mismatch). IB coverage is claimed only as checked in `IB_FOUNDATIONS.md`.
- **Plans** (`plans/`): decisions and acceptance criteria, not essays; every slice ends with an
  Acceptance block (exact test files and commands, 3-5 yes/no checks), per the autopilot skill.
- **The autopilot journal** is one file per tick in `journal/` (from `journal/_template.md`;
  numbers written by `scripts/tick_metrics.py`); `AUTOPILOT_JOURNAL.md` is a closed archive.
- **`LEARNING_LOG.md`**: after a merge an entry is written as a draft (heading tagged `DRAFT`,
  listed under "Open decisions"); only the author removes the tag.
