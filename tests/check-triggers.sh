#!/usr/bin/env bash
# Check which skills Claude Code loads for each test prompt.
# Usage: tests/check-triggers.sh [runs-per-prompt]   (default 2)
# Installs this checkout's plugins into a throwaway config, so your own
# Claude settings are untouched. Each run is one short Claude Code session.
set -euo pipefail
REPO=$(cd "$(dirname "$0")/.." && pwd); RUNS=${1:-2}
export CLAUDE_CONFIG_DIR=$(mktemp -d)
claude plugin marketplace add "$REPO" >/dev/null
for p in $(python3 -c "import json;print(' '.join(x['name'] for x in json.load(open('$REPO/.claude-plugin/marketplace.json'))['plugins']))"); do
  claude plugin install "$p@kays-lab-skills" >/dev/null
done
while IFS=$'\t' read -r id prompt; do
  want=$(grep -P "^$id\t" "$REPO/tests/expected.tsv" | cut -f2)
  for r in $(seq "$RUNS"); do
    got=$(cd "$(mktemp -d)" && timeout 240 claude -p "$prompt" --output-format stream-json --verbose --max-turns 3 2>/dev/null \
      | grep -o '"skill":"[^"]*"' | sed 's/"skill":"//;s/"//' | sort -u | tr '\n' ' ')
    miss=""; for w in $want; do [[ " $got " == *" $w "* ]] || miss+="$w "; done
    printf '%-8s run %s  %-4s  loaded: %s\n' "$id" "$r" "$([ -z "$miss" ] && echo PASS || echo FAIL)" "$got"
  done
done < "$REPO/tests/trigger_prompts.tsv"
