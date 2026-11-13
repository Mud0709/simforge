## What this is
<!-- One capability per PR. Two or three sentences: what changed and why it matters. -->

## Every task updates everything
<!-- Tick what applies; write "n/a" after a box that does not. From CLAUDE.md. -->
- [ ] Code, with tests written first against independent references (closed forms, limits,
      invariants, hand-worked values), each tolerance justified in a comment
- [ ] `SCIENTIFIC_VALIDATION.md`: what is proved, tested or only observed; measured numbers
      with the machine and date
- [ ] `ROADMAP.md` status (✅ / 🔜) where a step finished or started
- [ ] `ARCHITECTURE.md` and `README.md` where structure, decisions or usage changed
- [ ] The relevant learning guide (chapter, checkpoint, exercises); excerpts match their
      source (`python3 scripts/check_excerpts.py`)
- [ ] `docs/INDEX.md` regenerated (`python3 scripts/doc_index.py`)
- [ ] API contract regenerated if a schema changed (`make api-types`)
- [ ] Model version bumped and golden runs re-pinned if any output of a released model changed
- [ ] `docs/HANDOFF.md` rewritten: next action, open decisions, learning handoff
- [ ] `docs/LEARNING_LOG.md`: no entry still marked `DRAFT` that the author has not read
      (approve it by removing the tag, or edit it, before merging to `main`)

## Reviews
- [ ] Fresh-context review of each risky slice (scientific core, inputs and limits, stored
      data) and one of the PR; findings fixed or listed below

## Checks run
<!-- Only what actually ran, with results. Say what did not run and why. -->
- `scripts/check.sh --e2e`:

## Not in this PR / open decisions
<!-- What was left out on purpose, and anything the author must decide (also in HANDOFF). -->
