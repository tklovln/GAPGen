#!/usr/bin/env bash
# Keep this paper branch, its GitHub copy and its Overleaf project in step.
#
#   bash sync.sh setup              once per machine: Overleaf remote, token, first link
#   bash sync.sh status             where local, GitHub and Overleaf stand (changes nothing)
#   bash sync.sh pull               merge Overleaf web edits and GitHub commits into HEAD
#   bash sync.sh push -m "message"  commit, pull, check_paper.py --draft, push to both
#                [--no-check]       skip the compile gate (deliberate WIP only)
#
# Overleaf facts this script is built around:
#   * One Overleaf project is one git repo with a single branch, `main`: no
#     branches, tags, LFS or symlinks. Hence one paper branch per project.
#   * Web edits arrive as "Update on Overleaf." commits on top of the last push,
#     so fetch + merge brings them in like any collaborator's commits.
#   * History only moves forward: every push here fast-forwards both remotes.
#     A force-push would silently discard the user's web edits.
#   * Overleaf drops execute bits, so this file is committed 100644 and run as
#     `bash sync.sh`.
set -euo pipefail

BRANCH="aaie2027"
GITHUB_REMOTE="origin"
OVERLEAF_REMOTE="overleaf-aaie2027"
OVERLEAF_BRANCH="main"
OVERLEAF_PROJECT_ID="6ad762381d147d7d0c1ee34f"   # https://www.overleaf.com/project/<ID>
TOKEN_FILE="$HOME/.config/overleaf/git-credentials"   # outside the repo, chmod 600

export GIT_TERMINAL_PROMPT=0   # fail fast instead of hanging on a password prompt

SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
cd "$(dirname "$SELF")"

GH_REF="refs/remotes/$GITHUB_REMOTE/$BRANCH"
OL_REF="refs/remotes/$OVERLEAF_REMOTE/$OVERLEAF_BRANCH"
RESUME="resolve the files 'git status' lists, git add them, git commit, then run 'bash sync.sh push'"

die()  { printf 'sync.sh: %s\n' "$*" >&2; exit 1; }
info() { printf '== %s\n' "$*"; }
has_ref() { git rev-parse --verify -q "$1" >/dev/null; }
short() { git rev-parse --short "$1"; }

on_branch() {
  local cur
  cur="$(git symbolic-ref --short -q HEAD || true)"
  [[ "$cur" == "$BRANCH" ]] || die "HEAD is on '${cur:-detached HEAD}', expected '$BRANCH'"
}

no_merge_in_progress() {
  [[ ! -e "$(git rev-parse --git-path MERGE_HEAD)" ]] || die "a merge is in progress: $RESUME"
}

clean_tree() {
  [[ -z "$(git status --porcelain)" ]] ||
    die "uncommitted changes: commit them with 'bash sync.sh push -m \"<what changed>\"'"
}

overleaf_remote_ready() {
  git remote get-url "$OVERLEAF_REMOTE" >/dev/null 2>&1 ||
    die "no '$OVERLEAF_REMOTE' remote on this machine: run 'bash sync.sh setup'"
}

fetch_all() {
  if git ls-remote --exit-code --heads "$GITHUB_REMOTE" "$BRANCH" >/dev/null; then
    git fetch --quiet "$GITHUB_REMOTE" "+refs/heads/$BRANCH:$GH_REF"
  fi
  git fetch --quiet "$OVERLEAF_REMOTE" "+refs/heads/$OVERLEAF_BRANCH:$OL_REF" ||
    die "fetch from Overleaf failed: token in $TOKEN_FILE expired, or wrong OVERLEAF_PROJECT_ID?"
}

# merge_into_head <ref> <label>: bring <ref> into HEAD, fast-forward when possible.
merge_into_head() {
  local ref="$1" label="$2"
  has_ref "$ref" || return 0
  git merge-base --is-ancestor "$ref" HEAD && return 0       # nothing new there
  git merge-base "$ref" HEAD >/dev/null ||
    die "$label shares no history with $BRANCH: run 'bash sync.sh setup' to link it"
  if git merge-base --is-ancestor HEAD "$ref"; then
    git merge --quiet --ff-only "$ref"
    info "fast-forwarded to $label ($(short "$ref"))"
  else
    git merge --quiet --no-edit -m "Merge $label into $BRANCH" "$ref" ||
      die "conflict merging $label: $RESUME"
    info "merged $label ($(short "$ref"))"
  fi
}

pull_all() {
  fetch_all
  merge_into_head "$GH_REF" "GitHub $GITHUB_REMOTE/$BRANCH"
  merge_into_head "$OL_REF" "Overleaf $OVERLEAF_BRANCH"
}

report() {   # report <ref> <label>
  local ref="$1" label="$2"
  if ! has_ref "$ref"; then
    printf '  %-24s (nothing pushed yet)\n' "$label"
  elif ! git merge-base "$ref" HEAD >/dev/null; then
    printf '  %-24s %s  NOT LINKED: no shared history, run setup\n' "$label" "$(short "$ref")"
  else
    printf '  %-24s %s  local is %s ahead, %s behind\n' "$label" "$(short "$ref")" \
      "$(git rev-list --count "$ref..HEAD")" "$(git rev-list --count "HEAD..$ref")"
  fi
}

cmd_status() {
  overleaf_remote_ready
  fetch_all
  info "local $(git symbolic-ref --short -q HEAD || echo 'detached HEAD') at $(short HEAD)"
  report "$GH_REF" "GitHub $GITHUB_REMOTE/$BRANCH"
  report "$OL_REF" "Overleaf $OVERLEAF_BRANCH"
  if [[ -z "$(git status --porcelain)" ]]; then
    echo "  working tree clean"
  else
    echo "  uncommitted:"; git status --short | sed 's/^/    /'
  fi
}

cmd_pull() {
  on_branch; no_merge_in_progress; clean_tree; overleaf_remote_ready
  pull_all
  info "local $BRANCH at $(short HEAD) contains GitHub and Overleaf"
}

cmd_push() {
  local msg="" check=1
  while (($#)); do
    case "$1" in
      -m) [[ $# -ge 2 && -n "$2" ]] || die "-m needs a message"; msg="$2"; shift 2 ;;
      --no-check) check=0; shift ;;
      *) die "unknown push option '$1'" ;;
    esac
  done
  on_branch; no_merge_in_progress; overleaf_remote_ready

  # 1. Commit local work. The whitelist .gitignore limits `add -A` to paper files.
  if [[ -n "$(git status --porcelain)" ]]; then
    [[ -n "$msg" ]] || die "uncommitted changes: pass -m \"<what changed>\""
    git add -A
    git commit --quiet -m "$msg"
    info "committed $(short HEAD): $msg"
  fi

  # 2. Bring in whatever landed on GitHub or Overleaf since the last sync.
  pull_all

  # 3. Gate: Overleaf only ever receives a paper that compiles.
  if ((check)); then
    info "python3 check_paper.py --draft"
    python3 check_paper.py --draft ||
      die "check failed: fix the FAIL lines, then rerun (--no-check only for a deliberate WIP push)"
  fi

  # 4. GitHub first (the backup), then Overleaf. Both are plain fast-forward pushes.
  git push --quiet -u "$GITHUB_REMOTE" "$BRANCH"
  git push --quiet "$OVERLEAF_REMOTE" "$BRANCH:$OVERLEAF_BRANCH" ||
    die "Overleaf rejected the push (edited in the browser just now?): rerun 'bash sync.sh push'"

  # 5. Verify against the remotes themselves, not our tracking refs.
  local head gh ol
  head="$(git rev-parse HEAD)"
  gh="$(git ls-remote "$GITHUB_REMOTE" "refs/heads/$BRANCH" | cut -f1)"
  ol="$(git ls-remote "$OVERLEAF_REMOTE" "refs/heads/$OVERLEAF_BRANCH" | cut -f1)"
  [[ "$gh" == "$head" && "$ol" == "$head" ]] ||
    die "after push: local ${head:0:7}, GitHub ${gh:0:7}, Overleaf ${ol:0:7} (expected all equal)"
  info "in sync: local, GitHub $GITHUB_REMOTE/$BRANCH and Overleaf $OVERLEAF_BRANCH all at ${head:0:7}"
}

cmd_setup() {
  [[ -n "$OVERLEAF_PROJECT_ID" ]] ||
    die "fill in OVERLEAF_PROJECT_ID at the top of sync.sh (from the project URL) first"
  local url="https://git@git.overleaf.com/$OVERLEAF_PROJECT_ID"

  # Remote URL carries no secret; the token comes from a credential file scoped
  # to git.overleaf.com, outside the repo.
  if git remote get-url "$OVERLEAF_REMOTE" >/dev/null 2>&1; then
    git remote set-url "$OVERLEAF_REMOTE" "$url"
  else
    git remote add "$OVERLEAF_REMOTE" "$url"
  fi
  git config "credential.https://git.overleaf.com.helper" "store --file=$TOKEN_FILE"

  if [[ ! -s "$TOKEN_FILE" ]]; then
    [[ -t 0 ]] || die "no Overleaf token in $TOKEN_FILE: run 'bash sync.sh setup' in a terminal to enter it"
    local token
    read -rsp "Overleaf Git token (Account Settings > Git Integration): " token; echo
    [[ -n "$token" ]] || die "empty token"
    mkdir -p "$(dirname "$TOKEN_FILE")"
    (umask 077; printf 'https://git:%s@git.overleaf.com\n' "$token" > "$TOKEN_FILE")
    unset token
  fi

  info "fetching Overleaf project $OVERLEAF_PROJECT_ID"
  git fetch --quiet "$OVERLEAF_REMOTE" "+refs/heads/$OVERLEAF_BRANCH:$OL_REF" ||
    die "cannot fetch from Overleaf: check the token in $TOKEN_FILE and OVERLEAF_PROJECT_ID"

  # First contact: a new blank Overleaf project has its own unrelated root commit
  # holding the template main.tex. Adopting it as a merge parent with `-s ours`
  # keeps this branch's content and makes every later push a fast-forward.
  if has_ref "$OL_REF" && ! git merge-base "$OL_REF" HEAD >/dev/null; then
    on_branch; no_merge_in_progress; clean_tree
    local files
    files="$(git ls-tree -r --name-only "$OL_REF")"
    [[ "$files" == "main.tex" ]] || die "the Overleaf project holds more than the blank template:
$files
merge it by hand instead of discarding it: git merge --allow-unrelated-histories $OL_REF"
    git merge --quiet -s ours --allow-unrelated-histories \
      -m "Link Overleaf project: adopt its blank-template root, keep $BRANCH content" "$OL_REF"
    info "linked: Overleaf's blank template adopted as history, $BRANCH content kept"
  fi
  info "setup done; publish with: bash sync.sh push"
}

case "${1:-help}" in
  setup)  cmd_setup ;;
  status) cmd_status ;;
  pull)   cmd_pull ;;
  push)   shift; cmd_push "$@" ;;
  help|-h|--help) sed -n '2,/^set -euo pipefail/p' "$SELF" | sed '$d; s/^# \{0,1\}//' ;;
  *) die "unknown command '$1' (see: bash sync.sh help)" ;;
esac
