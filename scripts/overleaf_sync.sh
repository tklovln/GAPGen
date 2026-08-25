#!/usr/bin/env bash
# Build/refresh the `overleaf` branch: a paper-only orphan branch safe to push to Overleaf.
#
# Why an orphan branch: Overleaf's Git integration has no branches and no LFS, and
# syncing pushes whole-tree contents. A normal branch drags this repo's history
# (634M generated_art, 141M godot_demo) along with it. An orphan branch shares no
# history, so a push transfers only the files listed in FILES below.
#
# Why plumbing instead of `git switch`/`git worktree --orphan`: this repo has a 2.6G
# working tree with uncommitted work, and `--orphan` on worktree needs git >= 2.42
# (we have 2.39). Building the commit with a temporary index touches neither the
# real index, nor HEAD, nor a single file in the working tree.
#
# Usage:
#   scripts/overleaf_sync.sh              # refresh the branch from the working tree
#   scripts/overleaf_sync.sh --dry-run    # list what would be included, change nothing
#
# Then, once per machine:
#   git remote add overleaf https://git.overleaf.com/<PROJECT_ID>
#   git push overleaf overleaf:main       # local `overleaf` -> Overleaf's `main`
#
# Pulling Overleaf edits back:
#   git fetch overleaf main:refs/heads/overleaf-incoming
#   git diff overleaf overleaf-incoming   # review, then fast-forward `overleaf`

set -euo pipefail

BRANCH="overleaf"
MAX_MB=10          # refuse any single file larger than this (Overleaf has no LFS)
MAX_TOTAL_MB=50    # refuse a tree larger than this (the whole point of the branch)

# Paper sources, flattened to the Overleaf project root. Overleaf detects the main
# document by \documentclass, so a flat root is the least surprising layout.
# Deliberately excluded: paper/results (JSON/notes, not compiled), paper/human_eval
# (7.3M survey assets), paper/research-paper-writing (style guide), *.md, .DS_Store,
# neurips_2026.tex (upstream template demo, not our paper).
FILES=(
  "paper/main.tex:main.tex"
  "paper/refs.bib:refs.bib"
  "paper/neurips_2026.sty:neurips_2026.sty"
  "paper/checklist.tex:checklist.tex"
)
DIRS=(
  "paper/figures:figures"          # png only; the make_*.py generators stay out
)

cd "$(git rev-parse --show-toplevel)"

DRY=0
[[ "${1:-}" == "--dry-run" ]] && DRY=1

TMPIDX="$(mktemp -t overleaf-idx.XXXXXX)"
rm -f "$TMPIDX"                     # git wants to create it itself
trap 'rm -f "$TMPIDX"' EXIT
export GIT_INDEX_FILE="$TMPIDX"

total=0
added=0

stage() {   # stage <source-path> <dest-path-in-overleaf-project>
  local src="$1" dst="$2"
  [[ -f "$src" ]] || { echo "  skip (missing): $src" >&2; return 0; }
  local bytes mb
  bytes=$(wc -c < "$src" | tr -d ' ')
  mb=$(( bytes / 1048576 ))
  if (( mb >= MAX_MB )); then
    echo "REFUSING: $src is ${mb}MB (limit ${MAX_MB}MB, Overleaf has no LFS)" >&2
    exit 1
  fi
  total=$(( total + bytes ))
  added=$(( added + 1 ))
  if (( DRY )); then
    printf '  %-46s -> %s (%s bytes)\n' "$src" "$dst" "$bytes"
    return 0
  fi
  local blob
  blob=$(git hash-object -w "$src")
  git update-index --add --cacheinfo "100644,$blob,$dst"
}

echo "Staging paper sources for branch '$BRANCH':"
for pair in "${FILES[@]}"; do
  stage "${pair%%:*}" "${pair##*:}"
done
for pair in "${DIRS[@]}"; do
  srcdir="${pair%%:*}"; dstdir="${pair##*:}"
  # Only figure images. Generator scripts belong on main, not in the Overleaf project.
  while IFS= read -r f; do
    stage "$f" "$dstdir/$(basename "$f")"
  done < <(find "$srcdir" -maxdepth 1 -type f \
             \( -name '*.png' -o -name '*.pdf' -o -name '*.jpg' \) | sort)
done

total_mb=$(( total / 1048576 ))
echo "  ${added} files, ${total_mb}MB total"

if (( total_mb >= MAX_TOTAL_MB )); then
  echo "REFUSING: tree is ${total_mb}MB (limit ${MAX_TOTAL_MB}MB). The point of this" >&2
  echo "branch is to keep the monorepo off Overleaf -- check the FILES/DIRS lists." >&2
  exit 1
fi

if (( DRY )); then
  echo "Dry run: nothing written. HEAD and working tree untouched."
  exit 0
fi

tree=$(git write-tree)

# Orphan on first run; afterwards keep a linear history on the branch so Overleaf
# (which cannot handle non-linear history) always fast-forwards.
if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
  parent=$(git rev-parse "refs/heads/$BRANCH")
  if [[ "$(git rev-parse "$BRANCH^{tree}")" == "$tree" ]]; then
    echo "No changes; '$BRANCH' already at this tree ($(git rev-parse --short "$BRANCH"))."
    exit 0
  fi
  commit=$(git commit-tree "$tree" -p "$parent" -m "Sync paper sources from $(git rev-parse --short HEAD)")
else
  echo "Creating '$BRANCH' as an orphan branch (no shared history with main)."
  commit=$(git commit-tree "$tree" -m "Paper sources for Overleaf (orphan; no monorepo history)")
fi

git update-ref "refs/heads/$BRANCH" "$commit"
echo "Branch '$BRANCH' -> $(git rev-parse --short "$BRANCH")"
echo
echo "Verify it carries no monorepo baggage:"
echo "  git ls-tree -r --name-only $BRANCH"
echo "  git log --oneline $BRANCH        # should show only paper commits"
echo
echo "Push to Overleaf (local '$BRANCH' -> Overleaf's 'main'):"
echo "  git push overleaf $BRANCH:main"
