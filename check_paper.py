#!/usr/bin/env python3
"""Compile the paper on this branch and fail loudly on submission-blocking defects.

Checks the venue rules that a compile alone cannot catch: the page range, the
required template, double-blind anonymity (source and printed reference list),
draft placeholders left in the text, and placeholder bibliography entries.

    python3 check_paper.py             # submission mode: every violation FAILs
    python3 check_paper.py --draft     # sync mode: only a broken build FAILs,
                                       #   rule violations print as WARN
    python3 check_paper.py --no-build  # re-check existing logs, no compile

`bash sync.sh push` runs --draft: a half-written paper must still reach Overleaf,
but one that does not compile must not. Run the strict mode before any upload.

Requires `tectonic` (0.15+) on PATH or at ~/.local/bin/tectonic. Stdlib only.
Tectonic is XeTeX-based while Overleaf compiles with pdfLaTeX, so line breaks can
differ slightly: a page count sitting exactly at a limit is Overleaf's call.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Venues that exclude references count the body only. For those we read the page
# of the \label{endofbody} marker (placed just before \bibliography) out of the
# .aux file, which is LaTeX's own answer rather than our guess at where the
# references start.
BODY_LABEL = "endofbody"

# One entry per paper this branch submits. workshop.tex (published) and
# creativeai.tex are frozen reference copies, so they are deliberately absent.
PAPERS = {
    "main.tex": {
        # AAIE 2027, icaaie.org (read 2026-10-20): IEEE conference template,
        # double-blind review, 5-12 pages INCLUDING tables, figures and
        # references. Registration covers 5 pages; each further page is an
        # overlength charge of USD 60.
        "venue": "AAIE 2027 (IEEE conference, double-blind)",
        "total_pages": (5, 12),
        "paid_pages": 5,
        "template": "IEEEtran",  # name in \usepackage{..} or \documentclass{..}
        "blind": True,
    },
}

# Strings that must never reach a double-blind PDF. Extend as co-authors join.
IDENTIFIERS = ["tkwang", "Ting-Kang", "Gamania", "gmail.com", "Match3_sim"]

# Draft markers defined in main.tex for numbers and claims that wait for the
# experiments. Any use outside their \newcommand definition blocks submission.
PLACEHOLDER_MACROS = ["pending", "tbd"]

# Placeholder bib entries compile cleanly and print into the reference list, so
# only a content check catches them. "X Authors" is how the stubs were written.
BIB_PLACEHOLDERS = [
    r"author\s*=\s*\{\{[^}]*Authors\}\}",
    r"note\s*=\s*\{Replace with",
    r"\bTODO\b",
]


def find_tectonic() -> str | None:
    found = shutil.which("tectonic")
    if found:
        return found
    local = Path.home() / ".local" / "bin" / "tectonic"
    return str(local) if local.exists() else None


def compile_tex(tectonic: str, tex: Path) -> None:
    subprocess.run(
        [tectonic, "-X", "compile", tex.name, "--keep-logs", "--keep-intermediates"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )


def body_pages(tex: Path) -> int | None:
    """Page of \\label{endofbody} from the .aux, i.e. the last page of the body.

    \\newlabel{endofbody}{{<num>}{<page>}...} -- field 2 is the page. Returns None
    when the label is absent, which the caller must treat as a failure rather
    than a pass: an unverifiable page count is the situation this guard exists for.
    """
    aux = tex.with_suffix(".aux")
    if not aux.exists():
        return None
    m = re.search(
        r"\\newlabel\{" + re.escape(BODY_LABEL) + r"\}\{\{[^}]*\}\{(\d+)\}",
        aux.read_text(errors="replace"),
    )
    return int(m.group(1)) if m else None


def placeholders(src: str) -> int:
    """Uses of the draft macros, ignoring comments and their \\newcommand lines."""
    lines = [re.sub(r"(?<!\\)%.*", "", ln) for ln in src.splitlines()]
    body = "\n".join(ln for ln in lines if "\\newcommand" not in ln)
    return sum(len(re.findall(r"\\" + m + r"(?![A-Za-z])", body)) for m in PLACEHOLDER_MACROS)


def check(tex_name: str, cfg: dict, tectonic: str | None) -> tuple[list[str], list[str]]:
    """Return (build failures, rule violations) for one paper.

    A build failure means there is no trustworthy PDF; it fails in every mode.
    A rule violation fails only in submission mode. `tectonic=None` skips the
    compile and re-reads the existing logs.
    """
    tex = ROOT / tex_name
    if not tex.exists():
        return [f"{tex_name}: missing"], []

    if tectonic:
        try:
            compile_tex(tectonic, tex)
        except subprocess.CalledProcessError as e:
            tail = e.stderr.decode(errors="replace").strip().splitlines()[-15:]
            return [f"{tex_name}: tectonic failed\n    " + "\n    ".join(tail)], []

    log = tex.with_suffix(".log")
    if not log.exists():
        return [f"{tex_name}: no .log (compile first, drop --no-build)"], []
    log_text = log.read_text(errors="replace")
    src = tex.read_text(errors="replace")

    m = re.search(r"Output written on \S+ \((\d+) pages?", log_text)
    if not m:
        return [f"{tex_name}: could not read page count from log (no PDF written?)"], []
    total = int(m.group(1))

    rules: list[str] = []
    if "total_pages" in cfg:
        lo, hi = cfg["total_pages"]
        if not lo <= total <= hi:
            rules.append(f"{tex_name}: {total} pages outside the required {lo}-{hi} (references included)")
        extra = total - cfg.get("paid_pages", total)
        cost = f"; {extra} page(s) beyond the {cfg['paid_pages']} covered by registration" if extra > 0 else ""
        print(f"  pages: {total} / {lo}-{hi}   (references included{cost})")
    if "body_pages" in cfg:
        lo, hi = cfg["body_pages"]
        body = body_pages(tex)
        if body is None:
            rules.append(
                f"{tex_name}: no \\label{{{BODY_LABEL}}} found in .aux -- cannot tell "
                f"body pages from reference pages, so the {lo}-{hi} page rule is unverifiable"
            )
        else:
            if not lo <= body <= hi:
                rules.append(
                    f"{tex_name}: {body} body pages outside the required {lo}-{hi} "
                    f"(references and appendices excluded)"
                )
            print(f"  body pages: {body} / {lo}-{hi}   (PDF total {total}, refs excluded)")

    template = re.escape(cfg["template"])
    if not re.search(r"\\(?:usepackage|documentclass)(\[[^\]]*\])?\{" + template + r"\}", src):
        rules.append(f"{tex_name}: not using the required {cfg['template']} template")

    for pattern, label in [
        (r"^Overfull", "overfull box"),
        (r"Undefined control sequence", "undefined control sequence"),
        (r"(Reference|Citation) `[^']*' on page \d+ undefined", "undefined reference/citation"),
    ]:
        n = len(re.findall(pattern, log_text, re.MULTILINE))
        if n:
            rules.append(f"{tex_name}: {n} x {label}")

    # `??` in the PDF means a broken cross-reference that the log may not flag.
    if re.search(r"\\ref\{|\\cite\{", src) and "There were undefined references" in log_text:
        rules.append(f"{tex_name}: undefined references remain after final pass")

    n_ph = placeholders(src)
    if n_ph:
        rules.append(f"{tex_name}: {n_ph} draft placeholder(s) (\\pending, \\tbd) still in the text")

    if cfg["blind"]:
        hits = [i for i in IDENTIFIERS if i.lower() in src.lower()]
        if hits:
            rules.append(f"{tex_name}: double-blind but source contains {hits}")
        # The reference list is printed from the .bbl, not from the .tex.
        bbl = tex.with_suffix(".bbl")
        if bbl.exists():
            bbl_text = bbl.read_text(errors="replace").lower()
            hits = [i for i in IDENTIFIERS if i.lower() in bbl_text]
            if hits:
                rules.append(f"{tex_name}: double-blind but the reference list contains {hits}")

    n_cite = len(re.findall(r"\\cite[tp]?\b", src))
    print(f"  citations: {n_cite}", "  <-- WARNING: no related work" if n_cite == 0 else "")
    if n_ph:
        print(f"  draft placeholders: {n_ph}")
    return [], rules


def check_bibs() -> list[str]:
    """Placeholder entries compile cleanly and print into the reference list."""
    fails = []
    for bib in sorted(ROOT.glob("*.bib")):
        text = bib.read_text(errors="replace")
        for pat in BIB_PLACEHOLDERS:
            for m in re.finditer(pat, text):
                line = text[: m.start()].count("\n") + 1
                fails.append(f"{bib.name}:{line}: placeholder bib content {m.group(0)!r}")
    return fails


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--draft", action="store_true",
                    help="only a broken build fails; rule violations become warnings")
    ap.add_argument("--no-build", action="store_true", help="check existing logs only")
    args = ap.parse_args()

    tectonic = None
    if not args.no_build:
        tectonic = find_tectonic()
        if not tectonic:
            print("tectonic not found on PATH or at ~/.local/bin/tectonic", file=sys.stderr)
            return 2

    build_fails: list[str] = []
    rule_fails: list[str] = []
    for name, cfg in PAPERS.items():
        print(f"\n{name}  [{cfg['venue']}]")
        b, r = check(name, cfg, tectonic)
        build_fails += b
        rule_fails += r
    rule_fails += check_bibs()

    print()
    for f in build_fails:
        print("FAIL:", f)
    for f in rule_fails:
        print("WARN:" if args.draft else "FAIL:", f)
    if build_fails or (rule_fails and not args.draft):
        return 1
    if rule_fails:
        print(f"PASS (draft): compiles; {len(rule_fails)} rule violation(s) to fix before submitting")
    else:
        print("PASS: all papers compile and clear submission checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
