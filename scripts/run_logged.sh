#!/usr/bin/env bash
# Run a command with its whole output saved to a log, and print only a short digest:
#   scripts/run_logged.sh <name> '<command>'     e.g.  scripts/run_logged.sh pytest 'cd backend && uv run pytest tests/x -q'
# The log is $TICK_LOG_DIR (default /tmp/tick)/<name>.log and ends with an "exit: N" line, the
# format scripts/tick_metrics.py reads. The digest (status, counts, failing test names, first
# error lines) comes from `tick_metrics.py --summary`. Exit status is the command's.
# Rule: CLAUDE.md, "Test output".
set -u
[ $# -ge 2 ] || { echo "usage: $0 <name> '<command>'" >&2; exit 2; }
name=$1; shift
dir=${TICK_LOG_DIR:-/tmp/tick}
mkdir -p "$dir"
log="$dir/$name.log"
bash -c "$*" > "$log" 2>&1
code=$?
echo "exit: $code" >> "$log"
python3 "$(dirname "$0")/tick_metrics.py" --summary "$log"
exit "$code"
