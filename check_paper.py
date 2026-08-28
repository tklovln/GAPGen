#!/usr/bin/env python3
"""Compile every paper on this branch and fail loudly on submission-blocking defects.

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

# page_limit counts the whole PDF: neither venue's limit is exceeded by our
# reference lists, so the simpler whole-document count is the safe side to err on.
PAPERS = {
    "workshop.tex": {
        "venue": "NeurIPS 2026 Workshop: Who Verifies the Agents?",
        "page_limit": 9,
        "blind": True,
    },
    "main.tex": {
        "venue": "NeurIPS 2026 Creative AI Track",
        "page_limit": 9,
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
    if not m:
        fails.append(f"{tex_name}: could not read page count from log")
    else:
        pages = int(m.group(1))
        if pages > cfg["page_limit"]:
            fails.append(f"{tex_name}: {pages} pages exceeds limit {cfg['page_limit']}")
        print(f"  pages: {pages} / {cfg['page_limit']}")

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
