Delta Regeer's Resume
=====================

This repository contains my personal resume, typeset in LaTeX. There are some
Github Action automations too to allow me to easily build and publish updated
resumes, and it show cases part of my skillset of automation by publishing my
latest resume on-demand as a release on this repository.

For my latest resume, head over to:
https://github.com/digitalresistor/resume/releases and download the PDF
associated with the newest release!

Want to fork this repository for your own use case? Please do! Have changes to
the Github Actions? Shoot me over a pull request. Have questions? Reach out, I
swear I don't bite!

Cheers,
Delta Regeer


Layout
------

`resume.cls` holds the template and the reasoning behind every constraint it
enforces. `Resume.tex` holds only the content, so a diff that changes the resume
stays readable.


Building it
-----------

    make                  build Resume.pdf with a local pdflatex
    make lint             source-level checks, no build needed
    make check            build, then validate the PDF (Ghostscript only)
    make check-container  full validation in the CI image, both extractors

`make check-container` is the one that matches CI exactly. Prefer it over
installing poppler locally: on macOS `brew install poppler` pulls in a complete
GnuPG through `gpgme`, which shadows an existing MacGPG2 install and whose
agent takes over the sockets in `~/.gnupg`.

`pre-commit install` wires the source lint to commits, and the full build plus
validation to pushes. Hooks are a convenience, not a gate — CI is authoritative.


Why it is built the way it is
-----------------------------

This used to be a ModernCV document. It looked fine, but an Applicant Tracking
System never sees the rendered page — it reads the PDF's *text layer*, and that
text layer was badly broken:

* `efficiently` extracted as `efIciently`, because no ToUnicode CMap was
  emitted and the document ran in OT1.
* The email extracted as `#delta@regeer.org` — a FontAwesome glyph with no
  Unicode mapping, fused onto the address with no separator.
* Contact details existed *only* in the page footer, ~53 lines into the
  extracted text, and that footer was interleaved into the middle of the
  Experience section.
* Every entry was a two-column `tabular`, so dates sat in a different column
  from the roles they belonged to.

So there are rules now, and `make lint` / `make check` enforce them rather than
trusting anyone to remember them:

* **Single column.** No `tabular`, `multicolumn` or `minipage` in the content
  flow. Right-aligned dates use `\hfill` inside an ordinary paragraph.
* **No icon fonts.** Contact details are plain, extractable text.
* **`\input{glyphtounicode}` + `\pdfgentounicode=1`.** The single
  highest-value line in `resume.cls`.
* **No hyphenation.** `Kuber-\nnetes` does not match a search for `Kubernetes`.
* **`\rightskip` must be `plus 1fil`.** Given only a finite stretch, TeX
  shrinks interword spaces instead, and past a certain point extractors fuse
  the words together: `Workingacrossarangeofoperatingsystems`.
* **No running header or footer**, so nothing can repeat mid-document.
* **Two pages.** `make check` fails at three.

The font is Noto Sans. Font choice used to be badly constrained, because nearly
every sans broke extraction on the same character — the **ffi** ligature.
`efficient` came out as `efIcient` in Latin Modern, Computer Modern, CM Bright,
Iwona, Kurier, Fira Sans and Noto Sans, and as U+FB03 in Carlito, Lato and
Roboto. `Proficient`, which only has an *fi* ligature, was fine everywhere.
Disabling f-ligatures kills the whole class at once, so the font is now chosen
on looks.

One font property still matters, though. Text extractors infer word breaks from
the width of the interword space as encoded in the PDF, and those widths vary:

    Latin Modern Sans  -333/-367     Nimbus Sans  -278
    Noto Sans          -260          Source Sans Pro  -200

Source Sans Pro's 0.200 em space is narrow enough that Ghostscript merges every
word in the document — `DeltaRegeerefficient...`. That is a property of the
font rather than a quirk of one tool, so avoid it. Noto Sans sits in the normal
range and extracts cleanly in both engines.

`Dockerfile` names every package explicitly and uses `--no-install-recommends`.
The previous version named four packages and depended, invisibly, on apt
pulling `texlive-latex-extra` in as a *Recommends* of `texlive-fonts-extra` —
which was the only reason `moderncv.cls` was ever present. Adding
`--no-install-recommends`, ordinary hygiene, would have broken the build with
no hint in the file as to why.

The image is 2.58 GB, down from 3.95 GB. It would be 513 MB but for Noto Sans,
which needs `texlive-fonts-extra` for the font and `texlive-latex-extra` for
`fontaxes`. That is a deliberate trade of image size for typeface; switching
`resume.cls` back to `helvet` drops both packages.
