#!/usr/bin/env python3
"""Assert that the built resume PDF extracts as clean, correctly ordered text.

An Applicant Tracking System never sees the page you look at -- it sees the
PDF's text layer.  This script extracts that layer with every engine available
and asserts the result is something a parser can actually read.

Runs natively on macOS (Ghostscript only) and inside the CI image (Ghostscript
plus poppler).  Exit status 0 means every assertion held.

    python3 tools/ats_check.py --pdf Resume.pdf --log Resume.log
    python3 tools/ats_check.py --require gs,pdftotext      # CI: no silent skips

Deliberately absent: any check that the old name is *not* present.  Such a
check would need the string stored in this repo to match against, which would
undo commit b261de5.  check_metadata asserts /Author *equals* "Delta Regeer",
which is a strictly stronger guarantee and keeps the string gone.
"""

import argparse
import html
import os
import re
import shutil
import subprocess
import sys
import unicodedata
import zlib

# ---------------------------------------------------------------------------
# What the resume must say, verbatim.
# ---------------------------------------------------------------------------
NAME = "Delta Regeer"
EMAIL = "delta@regeer.org"
PHONE_RE = r"\+1\s*480[\s-]*264[\s-]*0039"
LINKS = ["digitalresistor.dev", "linkedin.com/in/deltaregeer", "github.com/digitalresistor"]

# The reading-order spine.  Every fragment must appear, in this order.  This
# single list simultaneously proves section order, entry order (including the
# deliberate APPA-before-Cruise sequence from commit 4868e5f), and that each
# role heading precedes its own bullets.
SPINE = [
    "Delta Regeer",
    "delta@regeer.org",
    "SUMMARY",
    "Delta has the ability to quickly understand data flow",
    "SKILLS",
    "EXPERIENCE",
    "Staff Engineer (DevSecOps)",
    "SAP, Sovereign Cloud",
    "highest level of engineering escalation",
    "Software/DevOps Consultant",
    "American Public Power Association",
    "custom user management web application",
    "Senior Security Engineer, Offensive Security",
    "Cruise LLC",
    "Offensive Security software",
    "Site Reliability Engineering Team Lead",
    "Crunch.io",
    "System Architect",
    "Centurylink",
    "PROJECTS",
    "Pylons Project",
    "DEF CON",
    "EDUCATION",
    "University of Advancing Technology",
]

# Role -> its own date.  If a template ever hoists dates into a separate
# column, the linearised text separates these two and the check fires.
ADJACENT = [
    ("Staff Engineer (DevSecOps)", "2020 - Present"),
    ("Software/DevOps Consultant", "2018 - 2020"),
    ("Senior Security Engineer, Offensive Security", "2019 - 2020"),
    ("Site Reliability Engineering Team Lead", "2016 - 2019"),
    ("System Architect", "2015 - 2016"),
    ("Bachelor of Science, Software Engineering", "2006 - 2009"),
]
ADJACENT_MAX_CHARS = 240

# Words carrying fi/ffi/fl ligatures.  If the ToUnicode CMap is wrong these
# are exactly what corrupts -- "efficiently" became "efIciently" in the
# moderncv build.
LIGATURE_WORDS = ["efficiently", "Proficient", "certify", "firefighting", "configurations"]

# Technology keywords an ATS would match on.  Also a regression net: if a
# future edit drops one of these, CI says so.
KEYWORDS = [
    "Rust", "Python", "Golang", "Kubernetes", "Terraform", "Keycloak",
    "PostgreSQL", "OpenStack", "SaltStack", "FedRAMP",
    "DNSSEC", "WebAuthn", "IPv6", "Squid", "Trivy", "Grype",
    "SAML", "Jenkins",
]

# Everything the extracted text may contain.  An allowlist, not a blocklist:
# this is what catches mojibake nobody thought to look for.
ALLOWED = (
    set(map(chr, range(0x20, 0x7F)))
    | {"\n", "\r", "\t"}
    | {
        "·",  # middle dot, the contact-line separator
        "–",  # en dash, the second-level bullet marker
        "’",  # right single quote, from ' in LaTeX
        "•",  # bullet, the first-level list marker
    }
)

FAILURES: list[str] = []
NOTES: list[str] = []


def fail(msg: str) -> None:
    FAILURES.append(msg)


def note(msg: str) -> None:
    NOTES.append(msg)


# ---------------------------------------------------------------------------
# Extractors
# ---------------------------------------------------------------------------
def gs_layout(pdf: str) -> str:
    """Layout-preserving extraction: line structure survives."""
    out = subprocess.run(
        ["gs", "-q", "-dNOPAUSE", "-dBATCH", "-sDEVICE=txtwrite",
         "-dTextFormat=3", "-sOutputFile=-", pdf],
        check=True, capture_output=True,
    ).stdout
    return out.decode("utf-8", errors="replace")


def gs_stream(pdf: str) -> str:
    """Content-stream order -- what a naive linearising parser sees.

    -dTextFormat=0 emits <span>/<char c="X"/> with bounding boxes.  Joining
    chars within a span and separating spans with a space reproduces the
    reading order the PDF actually encodes, independent of visual layout.
    """
    raw = subprocess.run(
        ["gs", "-q", "-dNOPAUSE", "-dBATCH", "-sDEVICE=txtwrite",
         "-dTextFormat=0", "-sOutputFile=-", pdf],
        check=True, capture_output=True,
    ).stdout.decode("utf-8", errors="replace")

    parts: list[str] = []
    for tag, char in re.findall(r"<(span|page)\b[^>]*>|<char\b[^>]*\bc=\"(.*?)\"\s*/>", raw):
        if tag == "page":
            parts.append("\n")
        elif tag == "span":
            parts.append(" ")
        elif char:
            parts.append(html.unescape(char))
    return "".join(parts)


def pdftotext(pdf: str, layout: bool = False) -> str:
    cmd = ["pdftotext", "-enc", "UTF-8", "-nopgbrk"]
    if layout:
        cmd.append("-layout")
    cmd += [pdf, "-"]
    return subprocess.run(cmd, check=True, capture_output=True).stdout.decode("utf-8", errors="replace")


def pagecount(pdf: str) -> int:
    out = subprocess.run(
        ["gs", "-q", "-dNODISPLAY", "-dBATCH", "-dNOSAFER",
         "-c", f"({pdf}) (r) file runpdfbegin pdfpagecount = quit"],
        check=True, capture_output=True,
    ).stdout.decode().strip()
    return int(out)


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------
def norm(text: str) -> str:
    return re.sub(r"[ \t\u00a0]+", " ", text.replace("\r\n", "\n").replace("\r", "\n"))



def flat(text: str) -> str:
    """Single-line form, for order and adjacency checks."""
    return re.sub(r"\s+", " ", norm(text)).replace("’", "'")


# Ghostscript's txtwrite has a flaky interword-space heuristic. pdfTeX emits an
# identical -278 offset for the space in all three of these:
#     [(TECHNICAL)-278(SKILLS)]TJ            -> gs drops the space
#     [(System)-278(Ar)20(c)10(hitect)]TJ    -> gs drops the space
#     [(Staff)-278(Engineer)-278(...)]TJ     -> gs keeps both spaces
# The PDF is correct and poppler reads all three correctly, so word-level
# assertions are authoritative only against poppler. Ghostscript still earns
# its place as a second, independent implementation for character-level
# corruption, and its word checks run with whitespace stripped from both sides
# so real damage is caught while the space heuristic is tolerated.
SPACE_FLAKY = {"gs-layout", "gs-stream"}


def hay(text: str, strict: bool) -> str:
    f = flat(text)
    return f if strict else re.sub(r"\s+", "", f)


def needle(s: str, strict: bool) -> str:
    return s if strict else re.sub(r"\s+", "", s)


# ---------------------------------------------------------------------------
# Assertions
# ---------------------------------------------------------------------------
def check_charset(tag: str, text: str) -> None:
    seen: dict[str, str] = {}
    for i, ch in enumerate(text):
        if ch not in ALLOWED and ch not in seen:
            seen[ch] = text[max(0, i - 30):i + 30].replace("\n", " ")
    for ch, ctx in list(seen.items())[:8]:
        fail(f"[{tag}] disallowed character U+{ord(ch):04X} "
             f"({unicodedata.name(ch, 'unnamed')}) in: ...{ctx.strip()}...")


def check_no_presentation_ligatures(tag: str, text: str) -> None:
    for ch in text:
        if 0xFB00 <= ord(ch) <= 0xFB06:
            fail(f"[{tag}] presentation-form ligature U+{ord(ch):04X}: the ToUnicode "
                 f"CMap maps ligatures to U+FB0x instead of decomposed ASCII")
            return


def check_contact(tag: str, text: str, strict: bool = True) -> None:
    f = hay(text, strict)

    hits = list(re.finditer(re.escape(needle(EMAIL, strict)), f))
    if not hits:
        fail(f"[{tag}] email {EMAIL} not present")
    else:
        if strict:
            # The moderncv build rendered this as "#delta@regeer.org", the
            # FontAwesome glyph fused onto the address with no separator.
            for m in hits:
                if m.start() and not f[m.start() - 1].isspace():
                    fail(f"[{tag}] email is glued to preceding text: "
                         f"{f[max(0, m.start() - 12):m.end()]!r}")
        if len(hits) != 1:
            fail(f"[{tag}] email appears {len(hits)}x, expected exactly 1 "
                 f"(a repeated running header/footer?)")

    n_phone = len(re.findall(needle(PHONE_RE, strict), f))
    if n_phone == 0:
        fail(f"[{tag}] phone number not present")
    elif n_phone != 1:
        fail(f"[{tag}] phone appears {n_phone}x, expected exactly 1")

    for link in LINKS:
        if needle(link, strict) not in f:
            fail(f"[{tag}] contact link {link!r} not present")


def check_contact_is_near_the_top(tag: str, text: str) -> None:
    """Parsers look for contact details at the head of the document.

    moderncv put them in the page footer, ~53 lines in.
    """
    lines = [ln for ln in norm(text).split("\n") if ln.strip()]
    head = "\n".join(lines[:10])
    if NAME not in "\n".join(lines[:3]):
        fail(f"[{tag}] {NAME!r} does not appear in the first 3 non-blank lines")
    if EMAIL not in head:
        fail(f"[{tag}] email does not appear in the first 10 non-blank lines")


def check_keywords(tag: str, text: str, strict: bool = True) -> None:
    f = hay(text, strict)
    for word in LIGATURE_WORDS + KEYWORDS:
        pat = rf"\b{re.escape(word)}\b" if strict else re.escape(word)
        if not re.search(pat, f, re.IGNORECASE):
            fail(f"[{tag}] keyword {word!r} missing, split or corrupted")


def check_no_line_end_hyphen(tag: str, text: str) -> None:
    for n, line in enumerate(norm(text).split("\n"), 1):
        s = line.rstrip()
        if s.endswith("-") and not s.endswith(" -"):
            fail(f"[{tag}] line {n} ends in a hyphen, so a word is split across "
                 f"lines and will not match as a keyword: {s[-46:]!r}")


def check_order(tag: str, text: str, strict: bool = True) -> None:
    f = hay(text, strict).upper()
    pos = -1
    for frag in SPINE:
        i = f.find(needle(frag, strict).upper(), pos + 1)
        if i < 0:
            fail(f"[{tag}] missing or out of reading order: {frag!r}")
            return
        pos = i


def check_adjacency(tag: str, text: str, strict: bool = True) -> None:
    f = hay(text, strict)
    for role, date in [(needle(r, strict), needle(d, strict)) for r, d in ADJACENT]:
        a, b = f.find(role), f.find(date)
        if a < 0:
            fail(f"[{tag}] cannot locate role {role!r}")
        elif b < 0:
            fail(f"[{tag}] cannot locate date {date!r}")
        elif not 0 < b - a < ADJACENT_MAX_CHARS:
            fail(f"[{tag}] date {date!r} is {b - a} chars from its role {role!r}; "
                 f"dates look hoisted into a separate column")


_PDF_ESCAPES = {b"n": b"\n", b"r": b"\r", b"t": b"\t", b"b": b"\b",
                b"f": b"\f", b"(": b"(", b")": b")", b"\\": b"\\"}


def _decode_pdf_string(s: bytes) -> str:
    """Decode a PDF literal string: octal escapes, then UTF-16BE or PDFDoc."""
    out = bytearray()
    i = 0
    while i < len(s):
        c = s[i:i + 1]
        if c != b"\\":
            out += c
            i += 1
            continue
        nxt = s[i + 1:i + 2]
        if nxt in _PDF_ESCAPES:
            out += _PDF_ESCAPES[nxt]
            i += 2
        elif nxt and nxt in b"01234567":
            digits = b""
            j = i + 1
            while j < len(s) and len(digits) < 3 and s[j:j + 1] in b"01234567":
                digits += s[j:j + 1]
                j += 1
            out.append(int(digits, 8) & 0xFF)
            i = j
        elif nxt in (b"\n", b"\r"):
            i += 2                      # escaped newline: line continuation
        else:
            out += nxt
            i += 2
    b = bytes(out)
    if b.startswith(b"\xfe\xff"):
        return b[2:].decode("utf-16-be", errors="replace")
    return b.decode("latin-1")


def _pdf_info_value(raw: bytes, key: str):
    """Return the /Key (...) literal string from the Info dict, decoded."""
    m = re.search(rb"/" + key.encode() + rb"\s*\(", raw)
    if not m:
        return None
    i = start = m.end()
    depth = 1
    while i < len(raw) and depth:
        c = raw[i:i + 1]
        if c == b"\\":
            i += 2
            continue
        if c == b"(":
            depth += 1
        elif c == b")":
            depth -= 1
        i += 1
    return _decode_pdf_string(raw[start:i - 1])


def _inflated(raw: bytes) -> bytes:
    """Every FlateDecode stream, inflated. Link annotations usually live in a
    compressed object stream, so a raw byte scan alone cannot see them."""
    chunks = []
    for m in re.finditer(rb"stream\r?\n", raw):
        end = raw.find(b"endstream", m.end())
        if end < 0:
            continue
        try:
            chunks.append(zlib.decompressobj().decompress(raw[m.end():end]))
        except zlib.error:
            pass
    return b"\n".join(chunks)


def check_metadata(pdf: str) -> None:
    raw = open(pdf, "rb").read()

    for key, want in (("Title", "Delta Regeer - Resume"), ("Author", NAME)):
        got = _pdf_info_value(raw, key)
        if got is None:
            fail(f"[meta] /{key} missing from the PDF Info dictionary")
        elif got != want:
            fail(f"[meta] /{key} is {got!r}, expected {want!r}")
    for key in ("Subject", "Keywords"):
        if _pdf_info_value(raw, key) is None:
            fail(f"[meta] /{key} missing from the PDF Info dictionary")

    haystack = raw + b"\n" + _inflated(raw)
    n_uri = len(re.findall(rb"/URI\s*[(<]", haystack))
    if n_uri < 5:
        fail(f"[meta] only {n_uri} link annotations found, expected at least 5")
    if b"mailto:" + EMAIL.encode() not in haystack:
        fail("[meta] mailto: link annotation missing")


def check_log(logfile: str) -> None:
    txt = open(logfile, encoding="utf-8", errors="replace").read()
    rules = [
        (r"^Overfull \\hbox", "overfull hbox, text runs into the margin"),
        (r"^! ", "LaTeX error"),
        (r"Missing character:", "a glyph is absent from the font"),
        (r"Font shape .* not available", "font-shape substitution"),
        (r"Font shape .* undefined", "undefined font shape"),
        (r"^LaTeX Warning: Reference", "unresolved reference, build is not single-pass"),
        (r"Rerun to get", "build is not single-pass"),
        (r"Type 3 font", "a bitmap font is embedded, text will not extract"),
    ]
    for pat, why in rules:
        for hit in re.findall(pat + r".*", txt, re.M)[:3]:
            fail(f"[log] {why}: {hit.strip()[:110]}")


def check_pages(pdf: str, maxpages: int) -> None:
    n = pagecount(pdf)
    size_kb = os.path.getsize(pdf) / 1024
    note(f"{n} pages, {size_kb:.0f} kB")
    if n > maxpages:
        fail(f"[pdf] {n} pages, maximum is {maxpages}")
    if size_kb > 2500:
        fail(f"[pdf] {size_kb:.0f} kB exceeds the 2.5 MB limit Greenhouse documents")


# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pdf", default="Resume.pdf")
    ap.add_argument("--log", default="Resume.log")
    ap.add_argument("--max-pages", type=int, default=2)
    ap.add_argument("--require", default="gs", help="comma separated: gs,pdftotext")
    args = ap.parse_args()

    if not os.path.exists(args.pdf):
        print(f"FATAL: {args.pdf} not found; build it first", file=sys.stderr)
        return 2

    available = {"gs": shutil.which("gs"), "pdftotext": shutil.which("pdftotext")}
    for req in {s.strip() for s in args.require.split(",") if s.strip()}:
        if not available.get(req):
            print(f"FATAL: required extractor {req!r} not found on PATH", file=sys.stderr)
            return 2

    extractions: list[tuple[str, str]] = []
    if available["pdftotext"]:
        extractions.append(("pdftotext", pdftotext(args.pdf)))
        extractions.append(("pdftotext-layout", pdftotext(args.pdf, layout=True)))
    else:
        # Deliberately not suggesting `brew install poppler` here: on macOS it
        # pulls a whole GnuPG in via gpgme, shadowing an existing MacGPG2 and
        # letting its agent take over ~/.gnupg. Use the container instead.
        note("pdftotext not found: word-level checks are running whitespace-insensitively. "
             "Run `make check-container` for the full-fidelity check.")
    if available["gs"]:
        extractions.append(("gs-layout", gs_layout(args.pdf)))
        extractions.append(("gs-stream", gs_stream(args.pdf)))
    else:
        note("ghostscript not found, skipping its extractions")

    for tag, text in extractions:
        strict = tag not in SPACE_FLAKY
        # Character-level checks are authoritative from every engine.
        check_charset(tag, text)
        check_no_presentation_ligatures(tag, text)
        # Word-level checks: strict against poppler, whitespace-insensitive
        # against Ghostscript. See the SPACE_FLAKY comment.
        check_contact(tag, text, strict)
        check_keywords(tag, text, strict)
        check_order(tag, text, strict)
        check_adjacency(tag, text, strict)
        if strict and tag != "gs-stream":
            check_contact_is_near_the_top(tag, text)
            check_no_line_end_hyphen(tag, text)

    check_metadata(args.pdf)
    if os.path.exists(args.log):
        check_log(args.log)
    else:
        note(f"{args.log} not found, skipping build-log checks")
    check_pages(args.pdf, args.max_pages)

    for n in NOTES:
        print(f"note: {n}")
    if FAILURES:
        print(f"\nATS CHECK FAILED -- {len(FAILURES)} problem(s):\n", file=sys.stderr)
        for f in FAILURES:
            print(f"  - {f}", file=sys.stderr)
        return 1
    print(f"\nATS CHECK PASSED ({len(extractions)} extractor(s): "
          f"{', '.join(t for t, _ in extractions)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
