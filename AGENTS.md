# Agent instructions — `overleaf` branch

This branch is **paper sources only**. It shares a working directory with `main`,
whose 2.6GB of assets sit here as untracked files. Read `.gitignore` before
changing what is tracked.

## Push rules

Two remotes, two different refspecs. Neither is `git push` with no arguments.

```bash
# 1. validate first -- never push a paper that has not compiled
python3 check_paper.py

# 2. GitHub backup (branch keeps its name)
git push origin overleaf

# 3. Overleaf project (local `overleaf` branch -> remote `main`)
git push overleaf overleaf:main
```

**Overleaf only accepts the branch named `main`.** Pushing `overleaf:master`, or
creating any new remote branch, is rejected with `remote: error: wrong branch`.
Overleaf has no branch support and no LFS, which is why this branch exists at all
rather than pushing the monorepo.

Check for divergence before pushing to Overleaf, because edits made in the
Overleaf web editor land as real commits on `overleaf/main`:

```bash
git fetch overleaf
git merge-base --is-ancestor overleaf/main HEAD   # exit 0 => fast-forward, safe
```

If that fails, Overleaf has commits this branch lacks. Merge them; do not
force-push, which silently discards the user's web edits.

## Never commit build artifacts

`.gitignore` ignores everything by default (`*`) and un-ignores only what LaTeX
needs, so new monorepo directories are covered without editing it. Two
consequences:

- A new file type that LaTeX *does* need (`AGENTS.md`, `*.cls`) requires an
  explicit `!` line, or it is invisible to git.
- **Ignore rules do not apply to already-tracked paths.** Build artifacts
  (`*.aux`, `*.log`, `*.bbl`, `*.blg`, `*.out`) and `.DS_Store` were once tracked
  despite matching `*`; they had to be removed with `git rm --cached`. Overleaf
  compiles from source, so a stale `.aux` or `.bbl` in the repo is a source of
  results that disagree with the sources. If `git ls-files` ever lists one again,
  untrack it.

## Validation

`check_paper.py` enforces the rules a compile alone does not catch: body length
within the venue's page range *excluding references*, the required
`neurips_2026` template, double-blind anonymity, and placeholder bibliography
entries. It needs `tectonic` on `PATH` (installed at `~/.local/bin/tectonic`).

Body length is read from the page of `\label{endofbody}`, which sits just before
`\bibliography` in each paper. **Do not delete that label** — the page rule
becomes unverifiable without it, and the checker fails rather than passes when it
is missing. When adding a paper here, add the label and a `PAPERS` entry.

## Secret

The `overleaf` remote URL embeds an Overleaf write token in `.git/config`. It is
not tracked, but do not echo `git remote -v` output into files, commits, or
anything shared.
