# Agent instructions — `aaie2027` branch

Paper sources for the AAIE 2027 submission, nothing else: *EduAssetVerify*, written
from `proposal.md` in the IEEE format of `latex-template/`. The branch descends from
`overleaf` (the published NeurIPS 2026 workshop paper) and lives in three places
that `sync.sh` keeps in step:

- **local**: this worktree; on the shared box `../GAPGen` holds `main` (code, results)
- **GitHub**: `origin/aaie2027`, the backup
- **Overleaf**: remote `overleaf-aaie2027`, branch `main`, where the user reads and edits

Venue (icaaie.org, read 2026-10-21): IEEE conference template, double-blind review,
submission deadline 2026-11-20, 5-12 pages *including* references; registration covers
5 pages, each further page costs USD 60. There is no separate supplementary upload, so the
appendix is part of the PDF and counts. The user's target is at most 5 pages before the
references; the current version is the 5-page paper (body and references end on page 5)
plus a one-page appendix the user approved (6 pages, USD 60 overlength).
`PAPERS` in `check_paper.py` encodes the body and total limits.

The appendix page: its two `figure*` (Figs. 5 and 6) are defined right after
`\label{endofbody}`, because a `figure*` never appears on the page where it is defined;
after the bibliography, `\newpage` (not `\clearpage`, which would flush them onto a float
page of their own) starts page 6 under them, and `\raggedbottom` keeps its half-empty
columns from stretching.

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
| `tables/{main,ablation,overview_values,split}.tex`, `figures/eav_examples.pdf`, `figures/eav_teaser_asset.png`, `figures/eav_overview_regions.png`, `figures/eav_domain_far.pdf`, `figures/eav_appendix_{pairs,bench,errors}.pdf` | generated from the experiment results on `main`; never edited by hand |
| Figs. 1 and 2 | TikZ in `main.tex`; palette `eav*` colors and the robot/ruler icons (TikZ pics) are defined in the preamble, which also inputs `tables/overview_values.tex`. Fig. 1 shows the rule-picked pie asset (`teaser()` in `eav/paper.py`); Fig. 2 follows the same asset through every module, and every value it prints (and Fig. 1's red witness box) is a macro from `overview_values.tex` (`overview()` in `eav/paper.py`: parser answers from the response cache, readings from the run record, rule pass recomputed and checked against the logged verdicts). Typed by hand from `numbers.json`: the 59% in Fig. 1's caption and its judges' range bar |
| Figs. 3 and 4 | `figures/eav_examples.pdf` (examples) and `figures/eav_domain_far.pdf` (false acceptance by domain under Claude only, which replaced the domain table; the Gemini maxima in its caption are `fig_domain` in `numbers.json`) |
| Appendix (page 6) | Figs. 5-7 and Table III: rule-picked counterfactual pairs (`fig_pairs`), templates and unseen styles (`fig_bench`), false acceptance by operator (`fig_errors`), pair accuracy per test condition (`tables/split.tex`); the counts in its text and the Fig. 7 caption are `appendix` in `numbers.json` |
| `check_paper.py` | compile + venue-rule check; `PAPERS` holds the rules for `main.tex` |
| `sync.sh` | the one path for commits between local, GitHub and Overleaf |

Frozen papers are reading material: mine them for technical lessons, edit `main.tex`.
`workshop.tex` is the source of the evaluation pitfalls the method and the guards table
build on; paraphrase it, since AAIE screens for similarity (index below 20%).

## Experiments

Code, benchmark builder and results live on `main` in `eduassetverify/` (worktree
`../GAPGen`); read its `CONFIG_FROZEN.md` before changing a setting. After any re-run:

```bash
cd ../GAPGen/eduassetverify && .venv/bin/python -m eav.paper --out results/paper
# then copy results/paper/tab_{main,ablation}.tex -> tables/ (keep the header comment),
# teaser_asset.png -> figures/eav_teaser_asset.png, overview_values.tex -> tables/overview_values.tex,
# overview_regions.png -> figures/eav_overview_regions.png,
# fig_examples.pdf -> figures/eav_examples.pdf, fig_domain_far.pdf -> figures/eav_domain_far.pdf,
# tab_split.tex -> tables/split.tex (keep the header comment),
# fig_{pairs,bench,errors}.pdf -> figures/eav_appendix_{pairs,bench,errors}.pdf
# (PDFs are gitignored on main, so the paper branch holds the only committed copy)
```

The project page is generated too: after `eav.paper`, run `.venv/bin/python -m eav.demo --out
results/demo` (its docstring lists what it checks), replace the files of the demo repository
`tklovln/eduassetverify-demo` (GitHub Pages from the root of `main`) with `results/demo/` while
keeping its README, and push. The anonymous mirror serves a new commit only after the user clicks
"Force update" in its dashboard.

Every number in the prose (abstract, introduction, Section VII, conclusion, appendix) is read from
`results/paper/numbers.json` on `main`; re-check the prose against it whenever a table
changes. Thresholds are fixed on the dev split only; a post-test change goes into
`CONFIG_FROZEN.md` and is disclosed in the paper.

## Rules

- **Numbers come from experiment outputs.** `\pending{...}` and `\tbd` mark any new
  claim or cell that waits for experiments; strict `check_paper.py` fails while one
  remains. Fill one only with a value produced by the evaluation code.
- **Report what the data say.** Negative and mixed results stay in the paper (judges
  beat us on accuracy under Gemini; the semantic verifier and abstention add nothing).
  A table may go for space or readability; its finding then stays in the text.
- **No learning-outcome claims.** Nothing here was tested on learners; statements stay
  about verifying assets, never about student understanding or achievement.
- **Double-blind.** The workshop paper is cited in the third person as
  `anon2026legibility`; author names, affiliations, links and acknowledgments stay
  out until camera-ready. `check_paper.py` scans the printed source (comments excluded)
  and the `.bbl`; its identifiers include the GitHub account `tklovln`. The user's
  project-page sentence after the contributions list links, for review, to the rendered page
  of the user's Anonymous GitHub mirror of the demo repository,
  `anonymous.4open.science/w/eduassetverify-demo/` (`/r/` would open its repository browser).
  `/w/` works only while "GitHub Pages" is ticked under Features in the mirror's settings, which
  only the user can change; the mirror masks the terms `tklovln` and `xdblazer39`. The mirror is
  outside `check_paper.py`; before upload, the page must load (`curl -s -H "Accept: text/html" -o /dev/null -w "%{http_code}"
  https://anonymous.4open.science/w/eduassetverify-demo/` prints 200; without that header the mirror
  answers 404, and 400 means page_not_activated) and
  no served file may name the account or carry the mirror's mask `XXXX-n` (this must print 0):
  `for f in $(for p in "" thumbs; do curl -s "https://anonymous.4open.science/api/repo/eduassetverify-demo/files?path=$p" | python3 -c "import json,sys; print(' '.join('/'.join(filter(None, (x['path'], x['name']))) for x in json.load(sys.stdin) if x.get('size')))"; done); do curl -s "https://anonymous.4open.science/api/repo/eduassetverify-demo/file/$f"; done | grep -c -i "tklovln\|xdblazer\|github\.io\|XXXX-[0-9]"`.
  Camera-ready: the GitHub Pages address of the demo repository.
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
