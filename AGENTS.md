# Agent instructions — `aaie2027` branch

Paper sources for the AAIE 2027 submission, nothing else. The branch descends from
`overleaf` (the published NeurIPS 2026 workshop paper) and lives in three places
that `sync.sh` keeps in step:

- **local**: this worktree; on the shared box `../GAPGen` holds `main` (code, results)
- **GitHub**: `origin/aaie2027`, the backup
- **Overleaf**: remote `overleaf-aaie2027`, branch `main`, where the user reads and edits

## Writing loop

1. `bash sync.sh pull` before editing: the user may have changed text in Overleaf.
   Done when it prints that local contains GitHub and Overleaf.
2. Edit `main.tex`, `refs.bib`, `figures/`.
3. `bash sync.sh push -m "<what changed>"`: commits, merges newer Overleaf edits,
   gates on `check_paper.py --draft`, pushes to GitHub, then to Overleaf.
   Done only when it prints `in sync: ... all at <sha>`.

`bash sync.sh status` shows where the three stand; `bash sync.sh help` lists options.

A merge conflict stops `pull`/`push` mid-merge, with the user's Overleaf edit on one
side: resolve each file `git status` lists, keeping the user's wording unless the
task says otherwise, then `git add`, `git commit`, `bash sync.sh push`.

## Files

| path | role |
|---|---|
| `main.tex` | the AAIE 2027 paper and Overleaf's main document; seeded from `workshop.tex` |
| `workshop.tex` | published NeurIPS 2026 workshop paper, frozen |
| `creativeai.tex` | NeurIPS 2026 Creative AI Track version (was `main.tex` on `overleaf`), frozen |
| `refs.bib`, `figures/` | shared by all three papers: extend, and keep what the frozen papers use |
| `check_paper.py` | compile + venue-rule check; `PAPERS` holds the rules for `main.tex` |
| `sync.sh` | the one path for commits between local, GitHub and Overleaf |

Frozen papers are reading material: mine them for text and numbers, edit `main.tex`.

## Rules

- **Fast-forward only.** Every push extends both remotes' history. `sync.sh` merges
  before it pushes and never force-pushes, because a force-push silently deletes the
  user's Overleaf edits; route every push through it.
- **Venue rules are placeholders.** `PAPERS` in `check_paper.py` and
  `\usepackage{neurips_2026}` in `main.tex` are inherited from the workshop. Once the
  AAIE 2027 call is known, change template, page range and blind flag together.
- **Strict check before upload.** `--draft` lets a half-written paper sync; a
  submission needs plain `python3 check_paper.py` to print `PASS`.
- **Keep `\label{endofbody}`** just before `\bibliography`: the page rule reads its
  page and fails as unverifiable without it.
- **The user's notes are LaTeX comments** (`% TK: ...`) in the source. Overleaf review
  comments live outside git, never reach you, and a git push can displace them.
- **The tracked set is a whitelist.** `.gitignore` starts with `*` and un-ignores
  paper file types, so a new file type needs its own `!` line. Build output stays
  untracked: if `git ls-files` lists a `.aux`, `.log`, `.bbl` or built `.pdf`,
  `git rm --cached` it.
- **Files are committed 100644.** Overleaf drops execute bits, so run tools as
  `bash sync.sh` and `python3 check_paper.py`.
- **Figures are rendered on `main`.** Generate them there, copy the png/pdf into
  `figures/`; generator scripts and raw results stay on `main`.

## Secrets

The Overleaf token is in `~/.config/overleaf/git-credentials`, the GitHub token in
`~/.git-credentials`; repo-local `credential.<url>.helper` entries feed them to git,
so remote URLs stay secret-free. Refer to these files by path only.

## New machine

`bash sync.sh setup` adds the Overleaf remote and credential helper, asks for the
token once, and links a fresh blank project. On the shared `/home/ubuntu` box, SSH to
GitHub authenticates as `y10ab1`, who cannot push here: `origin` is HTTPS with
`credential.https://github.com.helper store`, and commits carry repo-local
`user.name=tklovln`, `user.email=xdblazer39@gmail.com`.
