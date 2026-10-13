#!/usr/bin/env bash
# skill-sync.sh -- report or resolve drift between the lab skills repo and the
# two places skills are actually used: Claude Code's account skills and the
# Claude Science skill store.
#
# STATUS: UNVALIDATED. Written 2026-10-13 from inside a sandbox that cannot
# reach either store, so the paths below are unverified and the script has
# never been run. Check the paths it prints before trusting any copy.
#
# Why this exists: skill edits get made in whichever tool is in front of you,
# and the repo is the thing the lab shares. An edit that lands in one store and
# not the repo is invisible to everyone else and is silently reverted the next
# time someone installs the plugin.
#
#   ./scripts/skill-sync.sh              # report drift, change nothing
#   ./scripts/skill-sync.sh --pull NAME  # store -> repo, for one skill
#   ./scripts/skill-sync.sh --push NAME  # repo -> store, for one skill
#
# There is deliberately no bulk copy mode. Copying every skill in one direction
# is how you lose an edit someone else made in the other.

set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CODE_STORE="$HOME/.claude/skills"
SCI_STORE=$(ls -d "$HOME"/.claude-science/orgs/*/skills 2>/dev/null | head -1 || true)

repo_path() { find "$REPO/plugins" -mindepth 3 -maxdepth 3 -type d \
                -path "*/skills/$1" 2>/dev/null | head -1; }

compare() {  # name store_dir label
  local name="$1" store="$2" label="$3" rp
  rp=$(repo_path "$name")
  [ -z "$rp" ] && return 0
  if [ ! -d "$store/$name" ]; then
    printf '  %-34s %-14s absent\n' "$name" "$label"; return 0
  fi
  if diff -rq "$rp" "$store/$name" >/dev/null 2>&1; then
    printf '  %-34s %-14s in sync\n' "$name" "$label"
  else
    printf '  %-34s %-14s DRIFT\n' "$name" "$label"
    diff -rq "$rp" "$store/$name" 2>/dev/null | sed 's/^/      /'
  fi
}

case "${1:-}" in
  --pull|--push)
    [ $# -eq 2 ] && [ -n "$2" ] || { echo "need a skill name" >&2; exit 2; }
    name="$2"; rp=$(repo_path "$name")
    [ -n "$rp" ] || { echo "no such skill in repo: $name" >&2; exit 2; }
    echo "Which store? 1) Claude Code  $CODE_STORE/$name"
    echo "             2) Science      ${SCI_STORE:-<not found>}/$name"
    read -r -p "1 or 2: " which
    case "$which" in
      1) store="$CODE_STORE/$name" ;;
      2) store="${SCI_STORE:?Science store not found}/$name" ;;
      *) echo "aborted" >&2; exit 2 ;;
    esac
    if [ "$1" = "--pull" ]; then src="$store"; dst="$rp"; else src="$rp"; dst="$store"; fi
    echo; echo "FROM $src"; echo "TO   $dst"; echo
    diff -ru "$dst" "$src" 2>/dev/null | head -60 || true
    read -r -p "apply? (yes/N) " ok
    [ "$ok" = "yes" ] || { echo "aborted"; exit 0; }
    mkdir -p "$dst"; rsync -a --delete "$src"/ "$dst"/
    echo "done. Review with git diff before committing."
    ;;
  ""|--check)
    echo "repo:    $REPO/plugins"
    echo "code:    $CODE_STORE"
    echo "science: ${SCI_STORE:-<not found>}"
    echo
    for d in "$REPO"/plugins/*/skills/*/; do
      n=$(basename "$d")
      compare "$n" "$CODE_STORE" "claude-code"
      [ -n "$SCI_STORE" ] && compare "$n" "$SCI_STORE" "science"
    done
    ;;
  *) sed -n '2,24p' "${BASH_SOURCE[0]}"; exit 2 ;;
esac
