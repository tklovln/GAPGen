# Agent instructions — `aaie2027` branch

Paper sources for the AAIE 2027 submission, nothing else: *EduAssetVerify*, written
from `proposal.md` in the IEEE format of `latex-template/`. The branch descends from
`overleaf` (the published NeurIPS 2026 workshop paper) and lives in three places
that `sync.sh` keeps in step:

- **local**: this worktree; on the shared box `../GAPGen` holds `main` (code, results)
- **GitHub**: `origin/aaie2027`, the backup
- **Overleaf**: remote `overleaf-aaie2027`, branch `main`, where the user reads and edits

Venue (icaaie.org, read 2026-10-20): IEEE conference template, double-blind review,
5-12 pages *including* references; registration covers 5 pages, each further page
costs USD 60. `PAPERS` in `check_paper.py` encodes these rules.

## Writing loop

1. `bash sync.sh pull` before editing: the user may have changed text in Overleaf.
   Done when it prints that local contains GitHub and Overleaf.
2. Edit `main.tex`, `aaie2027.bib`, `figures/`.
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
| `main.tex` | the AAIE 2027 paper (IEEEtran) and Overleaf's main document |
| `aaie2027.bib` | its bibliography, IEEE style; every entry checked against its publisher record |
| `IEEEtran.cls` | copied unchanged from `latex-template/` (v1.8b) |
| `proposal.md`, `latex-template/` | the user's inputs: research proposal and the IEEE template to follow |
| `workshop.tex`, `creativeai.tex` | earlier papers, frozen; with `refs.bib`, `neurips_2026.sty`, `checklist.tex` |
| `check_paper.py` | compile + venue-rule check; `PAPERS` holds the rules for `main.tex` |
| `sync.sh` | the one path for commits between local, GitHub and Overleaf |

Frozen papers are reading material: mine them for technical lessons, edit `main.tex`.
`workshop.tex` is the source of the evaluation pitfalls the method and Table IV guard
against; paraphrase it, since AAIE screens for similarity (index below 20%).

## Rules

- **Numbers come from experiment outputs.** `\pending{...}` and `\tbd` mark every
  claim and table cell that waits for experiments; strict `check_paper.py` fails
  while any remain. Replace one only with a value produced by the evaluation code.
  Abstract, introduction and conclusion claim no outcome until Section VII has data.
- **No learning-outcome claims.** Nothing here was tested on learners; statements stay
  about verifying assets, never about student understanding or achievement.
- **Double-blind.** The workshop paper is cited in the third person as
  `anon2026legibility`; author names, affiliations, links and acknowledgments stay
  out until camera-ready. `check_paper.py` scans the source and the printed `.bbl`.
- **IEEE format as in the template.** Keep the template's preamble, margins, fonts and
  spacing; size the content to the page budget instead of `\vspace` or font tweaks.
  Table captions above in title case, figure captions below, `Fig.~\ref{...}`.
  `\usepackage[T1]{fontenc}` exists only so local XeTeX builds keep Times.
- **References are verified, not recalled.** Add an entry only after checking it at
  doi.org, the proceedings page, or arXiv. IEEEtran.bst ignores `doi`, so the DOI is
  printed through `note`; `\bstctlcite{IEEEexample:BSTcontrol}` gives "et al." after
  six authors. Write titles in sentence case and brace proper nouns.
- **Fast-forward only.** Every push extends both remotes' history. `sync.sh` merges
  before it pushes and never force-pushes, because a force-push silently deletes the
  user's Overleaf edits; route every push through it.
- **Strict check before upload.** `--draft` lets a half-written paper sync; a
  submission needs plain `python3 check_paper.py` to print `PASS`.
- **The user's notes are LaTeX comments** (`% TK: ...`) in the source. Overleaf review
  comments live outside git, never reach you, and a git push can displace them.
- **The tracked set is a whitelist.** `.gitignore` starts with `*` and un-ignores
  paper file types, so a new file type needs its own `!` line. Build output stays
  untracked: if `git ls-files` lists a `.aux`, `.log`, `.bbl` or built `.pdf`,
  `git rm --cached` it.
- **Files are committed 100644.** Overleaf drops execute bits, so run tools as
  `bash sync.sh` and `python3 check_paper.py`.
- **Figures are rendered on `main`.** Generate them there, copy the png/pdf into
  `figures/`; generator scripts and raw results stay on `main`. Figs. 1 and 2 are
  TikZ inside `main.tex`.

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
