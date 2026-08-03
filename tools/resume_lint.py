#!/usr/bin/env python3
"""Source-level assertions for the resume sources. No build, runs in ~10ms.

tools/ats_check.py proves the built PDF is clean. This proves the source can
still produce a clean PDF, which is the cheaper and earlier signal -- most of
the ways this resume broke before are visible right here in the source.

    python3 tools/resume_lint.py [Resume.tex resume.cls]

Comments are stripped before matching, so the design-rules comment block at
the top of resume.cls can name the very constructs it forbids.
"""

import os
import re
import sys

# (pattern, why it must not appear)
FORBIDDEN = [
    (r"\\cventry|\\cvitem|\\makecvtitle|\\moderncv|\\documentclass(\[[^]]*\])?\{moderncv\}",
     "moderncv relic. Its \\cvitem is a two-column paragraph tabular, which is "
     "what put every date in a separate column and broke reading order."),
    (r"\\begin\{tabular|\\multicolumn|\\begin\{minipage|\\begin\{tabbing",
     "table or box layout in the content flow. Parsers linearise these "
     "column-by-column; keep the text stream single-column and linear."),
    (r"fontawesome|academicons|\\faicon",
     "icon font. Icon glyphs have no Unicode mapping and fuse onto adjacent "
     "text: the old build extracted the email as '#delta@regeer.org'."),
    (r"\\vspace\*\{-",
     "negative vspace density hack. The moderncv version needed "
     "\\vspace*{-5.6em}; fix spacing in the macros instead."),
    (r"\\fancyfoot|\\fancyhead|\\pagestyle\{fancy",
     "running header/footer. The old footer was injected into the middle of "
     "the Experience section and repeated the contact block."),
    (r"--",
     "en/em dash ligature in the source. Dates use an ASCII hyphen with "
     "spaces ('2020 - Present') so every parser's date regex matches."),
    (r"deltaregeer\.com",
     "that site still carries the deadname; link digitalresistor.dev instead."),
    (r"\t",
     "literal tab character."),
]

# Required patterns, per file. The template lives in resume.cls and the content
# in Resume.tex, so each is checked for what it is actually responsible for.
REQUIRED = {
    "resume.cls": [
        (r"\\input\{glyphtounicode\}", "\\input{glyphtounicode}"),
        (r"\\pdfgentounicode=1", "\\pdfgentounicode=1"),
        (r"\\DisableLigatures", "\\DisableLigatures -- f-ligatures must stay off"),
        (r"\\pagestyle\{empty\}", "\\pagestyle{empty} -- no running header or footer"),
        (r"\\@rightskip", "\\@rightskip -- without it every bullet is justified"),
    ],
    "Resume.tex": [
        (r"\\documentclass\{resume\}", "\\documentclass{resume}"),
        (r"digitalresistor\.dev", "the digitalresistor.dev homepage"),
        (r"delta@regeer\.org", "the email address"),
        (r"\\resumeSection\{Summary\}", "the Summary section"),
        (r"\\resumeSection\{Skills\}", "the Skills section"),
        (r"\\resumeSection\{Experience\}", "the Experience section"),
        (r"\\resumeSection\{Projects\}", "the Projects section"),
        (r"\\resumeSection\{Education\}", "the Education section"),
    ],
}
DEFAULT_PATHS = ["Resume.tex", "resume.cls"]


def strip_comments(src: str) -> str:
    """Blank out LaTeX comments, preserving line numbering and \\% escapes."""
    out = []
    for line in src.split("\n"):
        i, n = 0, len(line)
        while i < n:
            if line[i] == "\\":
                i += 2
                continue
            if line[i] == "%":
                line = line[:i]
                break
            i += 1
        out.append(line)
    return "\n".join(out)


def main(argv: list[str]) -> int:
    paths = argv[1:] or DEFAULT_PATHS
    failures = []
    seen = set()

    for path in paths:
        try:
            src = open(path, encoding="utf-8").read()
        except OSError as exc:
            failures.append(f"{path}: {exc}")
            continue
        body = strip_comments(src)

        for pattern, why in FORBIDDEN:
            for m in re.finditer(pattern, body):
                line = body[:m.start()].count("\n") + 1
                failures.append(f"{path}:{line}: {m.group(0)!r} -- {why}")

        name = os.path.basename(path)
        seen.add(name)
        for pattern, what in REQUIRED.get(name, []):
            if not re.search(pattern, body):
                failures.append(f"{path}: missing {what}")

    # pre-commit only passes the files that changed, so absent ones are not an
    # error -- but a full run over the defaults should cover both.
    if set(paths) == set(DEFAULT_PATHS):
        for name in REQUIRED:
            if name not in seen:
                failures.append(f"{name}: not found")

    if failures:
        print(f"resume lint FAILED -- {len(failures)} problem(s):\n", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1
    print(f"resume lint passed ({', '.join(paths)})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
