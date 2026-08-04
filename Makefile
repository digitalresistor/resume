.PHONY: all check lint clean

# Local builds use MacTeX; CI builds inside the Docker image (see Dockerfile).
# Note that a local build can never catch a missing-dependency regression,
# because a full TeX Live install has every package. Only the Docker build
# proves the dependency set.
LATEX ?= pdflatex
LATEXFLAGS ?= -interaction=nonstopmode -halt-on-error

all: Resume.pdf

Resume.pdf: Resume.tex resume.cls
	$(LATEX) $(LATEXFLAGS) Resume.tex

# Prove the PDF's text layer is something an ATS can actually read.
#
# Two targets, because the two extractors are not equally available. Word-level
# assertions are only authoritative against poppler's pdftotext (see the
# SPACE_FLAKY note in tools/ats_check.py), and poppler is deliberately NOT a
# local dependency here: on macOS `brew install poppler` drags in a full GnuPG
# via gpgme, which shadows an existing MacGPG2 and whose agent takes over
# ~/.gnupg. The container already has poppler-utils, so use it instead.
#
#   make check            fast local run, Ghostscript only (reduced fidelity)
#   make check-container  full run, both extractors, identical to CI
check: Resume.pdf lint
	python3 tools/ats_check.py --pdf Resume.pdf --log Resume.log --require gs

CONTAINER ?= $(shell command -v docker >/dev/null 2>&1 && echo docker || echo podman)

check-container:
	$(CONTAINER) build -t pdftex:latest - < Dockerfile
	$(CONTAINER) run --rm -v "$(PWD):$(PWD)" -w "$(PWD)" pdftex:latest \
	    pdftex -fmt=pdflatex -interaction=nonstopmode -halt-on-error ./Resume.tex
	$(CONTAINER) run --rm -v "$(PWD):$(PWD)" -w "$(PWD)" pdftex:latest \
	    python3 tools/ats_check.py --pdf Resume.pdf --log Resume.log --require gs,pdftotext

# Source-level assertions only; no build required.
lint:
	python3 tools/resume_lint.py Resume.tex resume.cls

clean:
	rm -f Resume.aux Resume.log Resume.out Resume.pdf Resume.synctex.gz
