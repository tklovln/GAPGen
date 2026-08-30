#!/usr/bin/env python3
"""Compile every paper on this branch and fail loudly on submission-blocking defects.

Checks the NeurIPS 2026 Workshop rules that a compile alone cannot catch: body
length within 4-9 pages excluding references, the required template, double-blind
anonymity, and placeholder bibliography entries.

Run before any Overleaf push or OpenReview upload:

    python3 check_paper.py            # compile + check
    python3 check_paper.py --no-build # check existing logs only

Requires `tectonic` (any 0.15+). Stdlib only, no venv needed.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# NeurIPS 2026 Workshop "Who Verifies the Agents?" submission guidelines:
#   Format      4-9 pages EXCLUDING references and appendices; NeurIPS 2026
#               template; demo papers <= 4 pages.
#   Review      double blind.
#   Dual subm.  work under review or recently published elsewhere is welcome,
#               so there is nothing to check here -- no venue conflict exists.
#   Archival    non-archival; accepted papers appear on OpenReview only.
#
# The page count that matters therefore is not the PDF length. We read the page
# of the \label{endofbody} marker (placed just before \bibliography) out of the
# .aux file, which is LaTeX's own answer rather than our guess at where the
# references start.
BODY_LABEL = "endofbody"

PAPERS = {
    "workshop.tex": {
        "venue": "NeurIPS 2026 Workshop: Who Verifies the Agents?",
        "body_pages": (4, 9),  # demo track would be (1, 4)
        "blind": True,
    },
    "main.tex": {
        "venue": "NeurIPS 2026 Creative AI Track",
        "body_pages": (4, 9),
        "blind": False,  # single-blind track: author names are meant to be visible
    },
}

# Strings that must never reach a double-blind PDF. Extend as co-authors join.
IDENTIFIERS = ["tkwang", "Ting-Kang", "Gamania", "gmail.com", "Match3_sim"]

# Placeholder bib entries compile cleanly and print into the reference list, so
# only a content check catches them. "X Authors" is how the stubs were written.
BIB_PLACEHOLDERS = [
    r"author\s*=\s*\{\{[^}]*Authors\}\}",
    r"note\s*=\s*\{Replace with",
    r"\bTODO\b",
]


def compile_tex(tex: Path) -> None:
    subprocess.run(
        ["tectonic", "-X", "compile", str(tex.name), "--keep-logs", "--keep-intermediates"],
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


def check(tex_name: str, cfg: dict, build: bool) -> list[str]:
    tex = ROOT / tex_name
    fails: list[str] = []
    if not tex.exists():
        return [f"{tex_name}: missing"]

    if build:
        try:
            compile_tex(tex)
        except subprocess.CalledProcessError as e:
            tail = e.stderr.decode(errors="replace").strip().splitlines()[-15:]
            return [f"{tex_name}: tectonic failed\n    " + "\n    ".join(tail)]

    log = tex.with_suffix(".log")
    if not log.exists():
        return [f"{tex_name}: no .log (compile first, drop --no-build)"]
    log_text = log.read_text(errors="replace")
    src = tex.read_text(errors="replace")

    m = re.search(r"Output written on \S+ \((\d+) pages?", log_text)
    total = int(m.group(1)) if m else None
    if total is None:
        fails.append(f"{tex_name}: could not read page count from log")

    lo, hi = cfg["body_pages"]
    body = body_pages(tex)
    if body is None:
        fails.append(
            f"{tex_name}: no \\label{{{BODY_LABEL}}} found in .aux -- cannot tell "
            f"body pages from reference pages, so the {lo}-{hi} page rule is unverifiable"
        )
    else:
        if not lo <= body <= hi:
            fails.append(
                f"{tex_name}: {body} body pages outside the required {lo}-{hi} "
                f"(references and appendices excluded)"
            )
        print(f"  body pages: {body} / {lo}-{hi}   (PDF total {total}, refs excluded)")

    if not re.search(r"\\usepackage(\[[^\]]*\])?\{neurips_2026\}", src):
        fails.append(f"{tex_name}: not using the required NeurIPS 2026 template")

    for pattern, label in [
        (r"^Overfull", "overfull box"),
        (r"Undefined control sequence", "undefined control sequence"),
        (r"(Reference|Citation) `[^']*' on page \d+ undefined", "undefined reference/citation"),
    ]:
        n = len(re.findall(pattern, log_text, re.MULTILINE))
        if n:
            fails.append(f"{tex_name}: {n} x {label}")

    # `??` in the PDF means a broken cross-reference that the log may not flag.
    if re.search(r"\\ref\{|\\cite\{", src) and "There were undefined references" in log_text:
        fails.append(f"{tex_name}: undefined references remain after final pass")

    if cfg["blind"]:
        hits = [i for i in IDENTIFIERS if i.lower() in src.lower()]
        if hits:
            fails.append(f"{tex_name}: double-blind but source contains {hits}")

    n_cite = len(re.findall(r"\\cite[tp]?\b", src))
    print(f"  citations: {n_cite}", "  <-- WARNING: no related work" if n_cite == 0 else "")
    return fails


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
    ap.add_argument("--no-build", action="store_true")
    args = ap.parse_args()

    if not args.no_build and not shutil.which("tectonic"):
        print("tectonic not on PATH (try ~/.local/bin/tectonic)", file=sys.stderr)
        return 2

    all_fails: list[str] = []
    for name, cfg in PAPERS.items():
        print(f"\n{name}  [{cfg['venue']}]")
        all_fails += check(name, cfg, build=not args.no_build)
    all_fails += check_bibs()

    print()
    if all_fails:
        for f in all_fails:
            print("FAIL:", f)
        return 1
    print("PASS: all papers compile and clear submission checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
