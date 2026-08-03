%%% resume.cls -- single-column resume class built for machine readability
%%%
%%% Engine:   pdfTeX, pdflatex format, ONE pass. No .aux/.out round trip.
%%% Packages: article, inputenc, fontenc, noto-sans, geometry, xcolor,
%%%           microtype, hyperref. Nothing else -- see Dockerfile.
%%%
%%% Design rules. An Applicant Tracking System never sees the page you look
%%% at, it sees the PDF's text layer. Do not break these:
%%%   * single column; no tabular/multicolumn/minipage in the content flow
%%%   * no icon fonts; contact details are plain, extractable text
%%%   * no hyphenation across line breaks
%%%   * no running header or footer
%%% `make check' proves all of the above against the built PDF, and
%%% `make lint' proves them against the source.
%%%
%%% Content lives in Resume.tex. Everything here is machinery, so that a diff
%%% touching the resume itself stays readable.

\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{resume}[2026/08/03 v1.0 ATS-parseable single-column resume]
\DeclareOption*{\PassOptionsToClass{\CurrentOption}{article}}
\ProcessOptions\relax
\LoadClass[10pt,letterpaper]{article}

%%--------------------------------------------------------------------------
%% 1. Encoding and text-extraction fidelity.
%%    Must come before anything typesets a glyph.
%%--------------------------------------------------------------------------
\RequirePackage[utf8]{inputenc}
\RequirePackage[T1]{fontenc}

% Emit a ToUnicode CMap for every embedded font. Without this, ligatures and
% anything outside plain ASCII extract as garbage -- the previous moderncv
% build turned "efficiently" into "efIciently". Highest-value line in the file.
\input{glyphtounicode}
\pdfgentounicode=1

% glyphtounicode maps ligatures to decomposed ASCII, which is what we want:
% an ATS searching for "efficient" must match. Re-assert it and cover the
% f_i style glyph names some fonts use, so a ligature can never surface as
% U+FB01 regardless of which font ends up embedded.
\pdfglyphtounicode{ff}{0066 0066}
\pdfglyphtounicode{fi}{0066 0069}
\pdfglyphtounicode{fl}{0066 006C}
\pdfglyphtounicode{ffi}{0066 0066 0069}
\pdfglyphtounicode{ffl}{0066 0066 006C}
\pdfglyphtounicode{f_f}{0066 0066}
\pdfglyphtounicode{f_i}{0066 0069}
\pdfglyphtounicode{f_l}{0066 006C}
\pdfglyphtounicode{f_f_i}{0066 0066 0069}
\pdfglyphtounicode{f_f_l}{0066 0066 006C}

%%--------------------------------------------------------------------------
%% 2. Fonts. Noto Sans.
%%
%%    Font choice used to be severely constrained: nearly every sans broke
%%    text extraction, but always on the SAME character -- the ffi ligature.
%%    "efficient" came out as "efIcient" (Latin Modern, Computer Modern,
%%    CM Bright, Iwona, Kurier, Fira Sans, TeX Gyre Adventor, Noto Sans) or
%%    as U+FB03 (Carlito, Lato, Roboto). "Proficient", with only an fi
%%    ligature, was fine everywhere. Disabling f-ligatures outright (see
%%    \DisableLigatures below) fixes the whole class at once and frees the
%%    font choice entirely -- so this is now picked on looks.
%%
%%    One extraction property is still worth respecting: the width of the
%%    interword space as encoded in the PDF, since threshold-based text
%%    extractors infer word breaks from it. Measured from the TJ operators:
%%      Latin Modern Sans  -333/-367     Nimbus Sans  -278
%%      Noto Sans          -260          Source Sans Pro  -200
%%    Source Sans Pro's 0.200 em space is narrow enough that Ghostscript
%%    merges every word in the document ("DeltaRegeerefficient..."). That is
%%    a property of the font, not a quirk of one tool, so avoid it. Noto Sans
%%    sits in the normal range and extracts cleanly in both engines.
%%--------------------------------------------------------------------------
\RequirePackage[sfdefault]{noto-sans}
\renewcommand{\ttdefault}{pcr}   % never fall back to Type3 bitmaps

%%--------------------------------------------------------------------------
%% 3. Page. No header, no footer, no page number: nothing that could
%%    interleave repeated text into the middle of the extracted stream.
%%--------------------------------------------------------------------------
\RequirePackage[letterpaper,
                top=0.45in, bottom=0.45in, left=0.6in, right=0.6in]{geometry}
\pagestyle{empty}

\RequirePackage{xcolor}
% moderncv's orange was rgb(0.95,0.55,0.15): about 2.2:1 against white, too
% light to survive printing or photocopying. This keeps the identity at a
% legible contrast. Used only on the name and section rules, never body text.
\definecolor{accent}{HTML}{B34700}

\RequirePackage[protrusion=true,expansion=false]{microtype}

% Disable f-ligatures. An ffi ligature is a single glyph, and in most fonts it
% carries no usable ToUnicode mapping, so "efficient" extracts as "efIcient"
% or as U+FB03 -- either way it will not match a keyword search. Setting the
% words in separate glyphs costs a sliver of typographic polish at 10pt and
% removes the failure mode completely, for every font.
\DisableLigatures[f]{encoding = T1, family = *}

%%--------------------------------------------------------------------------
%% 4. Links. bookmarks=false is what keeps this a single-pass build: no .out
%%    file, so no "Rerun to get outlines right".
%%
%%    The document metadata itself -- pdftitle, pdfauthor, pdfkeywords -- is
%%    content, so Resume.tex sets it with \hypersetup.
%%--------------------------------------------------------------------------
\RequirePackage[
  bookmarks=false,
  hidelinks,
  breaklinks=true,
  pdfpagemode=UseNone,
  pdflang={en-US}
]{hyperref}

%%--------------------------------------------------------------------------
%% 5. Paragraph shape: ragged right, hyphenation off entirely.
%%    A word split as "Kuber-\nnetes" does not match the keyword
%%    "Kubernetes" in any ATS. Three independent mechanisms, so a stray
%%    package or \selectlanguage cannot quietly re-enable it:
%%      hyphenpenalty/exhyphenpenalty  make any hyphen break infinitely bad
%%      lefthyphenmin/righthyphenmin   make every word too short to hyphenate
%%      pretolerance                   makes TeX accept the no-hyphenation pass
%%    exhyphenpenalty is the one people forget: it stops "dual-stack" breaking
%%    after the hyphen you typed yourself, which is indistinguishable from
%%    real hyphenation once the text is extracted.
%%    Overfull boxes are avoided by giving \rightskip infinite stretch, never
%%    by allowing hyphenation.
%%
%%    \rightskip MUST be "plus 1fil", not a finite stretch. With a finite
%%    value, a line needing more slack than that has nowhere to put it, so
%%    TeX shrinks the interword spaces instead -- and once they shrink past a
%%    text extractor's threshold the words fuse together in the text layer:
%%    "Workingacrossarangeofoperatingsystems". Greenhouse lists exactly this
%%    class of damage as a parse failure. Infinite stretch absorbs any amount
%%    of slack, so interword spaces always keep their natural width.
%%--------------------------------------------------------------------------
\makeatletter
\newcommand{\resume@nohyphen}{%
  \hyphenpenalty=10000
  \exhyphenpenalty=10000
  \lefthyphenmin=62
  \righthyphenmin=62
}
% \@rightskip as well as \rightskip: LaTeX's \list restores \rightskip from
% \@rightskip when it starts, so setting only \rightskip leaves every bullet
% justified -- which is both uglier and risky, since justification shrinks
% interword spaces on tight lines and that is what fuses words together in
% the extracted text layer.
\newcommand{\resumeRaggedRight}{%
  \resume@nohyphen
  \@rightskip=\z@ \@plus 1fil
  \rightskip=\@rightskip
  \parfillskip=\z@ \@plus 1fil
}
\makeatother

\setlength{\parindent}{0pt}
\setlength{\parskip}{0pt}

% 4% tighter leading. This is what buys the two-page fit at 10pt; the
% alternatives were a 9.5pt body or cutting more content, both worse. If a
% future edit pushes to three pages, `make check' fails -- prefer trimming
% content over winding this down further, and never reintroduce negative
% \vspace hacks like the moderncv version's \vspace*{-5.6em}.
\linespread{0.96}\selectfont

\AtBeginDocument{\resumeRaggedRight}

\clubpenalty=10000
\widowpenalty=10000
% Loose lines are the deliberate price of no hyphenation, so do not report
% them. Overfull boxes are NOT silenced: \hfuzz is untouched and `make check'
% fails the build on any "Overfull \hbox" in the log.
\hbadness=10000
\vbadness=10000

%%--------------------------------------------------------------------------
%% 6. Element fonts
%%--------------------------------------------------------------------------
\newcommand{\resumeNameFont}{\bfseries\fontsize{20}{24}\selectfont}
\newcommand{\resumeContactFont}{\fontsize{9}{12}\selectfont}
\newcommand{\resumeSectionFont}{\bfseries\fontsize{10.5}{13}\selectfont}

%%--------------------------------------------------------------------------
%% 7. Structure. Everything below is single column. The only boxes used are
%%    \mbox and \raisebox; there is no tabular, tabbing, minipage or
%%    multicolumn anywhere, so the PDF content stream is strictly linear.
%%--------------------------------------------------------------------------
\makeatletter

% -- one line, #1 flush left, #2 flush right, without a table ---------------
%    Zeroing \parfillskip and \rightskip leaves \hfill as the only infinite
%    glue on the line, so it takes all the slack and #2 lands hard right.
%    This is the classic bug in hand-rolled resume templates: with LaTeX's
%    default \parfillskip=0pt plus 1fil, \hfill and \parfillskip are the same
%    order of infinity and split the slack evenly, leaving the date stranded
%    mid-line. Deliberately not \hbox to \linewidth, which overflows into the
%    margin the moment a role title grows.
%    Extracted stream order is #1 then #2, i.e. exactly the reading order.
\newcommand{\resume@line}[2]{%
  \par
  \begingroup
    \resume@nohyphen
    \rightskip=\z@
    \parfillskip=\z@
    #1\hfill#2\par
  \endgroup
}

% -- needspace, without needspace.sty --------------------------------------
\newcommand{\resume@needspace}[1]{%
  \begingroup
    \setlength{\dimen@}{#1}%
    \vskip\z@\@plus\dimen@
    \penalty-100
    \vskip\z@\@plus-\dimen@
    \vskip\dimen@
    \penalty9999
    \vskip-\dimen@
    \vskip\z@skip
  \endgroup
}

% -- section heading, without titlesec -------------------------------------
\newcommand{\resumeSection}[1]{%
  \par
  \addvspace{7\p@}%
  \resume@needspace{4\baselineskip}%
  {\color{accent}\resumeSectionFont\MakeUppercase{#1}}%
  \par\nobreak
  % Without \nointerlineskip the rule is pushed a full \baselineskip below the
  % heading, which reads as a stray gap rather than an underline.
  \nointerlineskip
  \vskip 2\p@
  \noindent{\color{accent}\rule{\linewidth}{0.7\p@}}%
  \par\nobreak
  \vskip 3\p@
  \nobreak
}

% -- name and contact block, immediately under the name --------------------
\newcommand{\resumeSep}{\ \textperiodcentered\ }
\newcommand{\resumeHeader}[2]{%
  \begingroup
    \parindent=\z@ \parskip=\z@
    \resume@nohyphen
    \centering
    {\color{accent}\resumeNameFont #1\par}%
    \vskip 4\p@
    {\resumeContactFont #2\par}%
  \endgroup
  \nointerlineskip
  \vskip 5\p@
  \noindent{\color{accent}\rule{\linewidth}{0.7\p@}}%
  \par
}

% -- an experience / education entry ---------------------------------------
%    #1 role  #2 organisation  #3 location  #4 dates
%    Renders as
%        Staff Engineer (DevSecOps)                       2020 - Present
%        SAP, Sovereign Cloud                        Reston, VA (Remote)
%    Extracted stream: role, dates, organisation, location. Linear, and each
%    date stays next to its own role rather than in a separate column.
\newcommand{\resumeEntry}[4]{%
  \par
  \addvspace{5\p@}%
  \resume@needspace{4\baselineskip}%
  \resume@line{\bfseries #1}{\bfseries\mbox{#4}}%
  % \slshape, not \itshape: some sans families ship an oblique rather than a
  % true italic, and asking for `it' then triggers a font-shape substitution
  % warning that tools/ats_check.py treats as a build failure.
  \resume@line{\slshape #2}{\slshape #3}%
  \nobreak
  \vskip 2\p@
  \nobreak
}

% -- bullets, two levels, without enumitem ---------------------------------
%    Level 1 is \textbullet -> U+2022, the one bullet character every parser
%    recognises as a list marker. Level 2 is \textendash -> U+2013.
%    Both are asserted by tools/ats_check.py's character allowlist.
\newcommand{\resume@listsetup}{%
  \resumeRaggedRight
  \setlength{\partopsep}{\z@}%
  \setlength{\parsep}{\z@}%
  \setlength{\itemindent}{\z@}%
  \setlength{\listparindent}{\z@}%
  \setlength{\rightmargin}{\z@}%
}

\newenvironment{resumeItems}
  {\begin{list}{\textbullet}{%
     \resume@listsetup
     \setlength{\topsep}{1.2\p@}%
     \setlength{\itemsep}{0.8\p@}%
     \setlength{\leftmargin}{1.3em}%
     \setlength{\labelwidth}{0.85em}%
     \setlength{\labelsep}{0.45em}%
   }}
  {\end{list}}

\newenvironment{resumeSubItems}
  {\begin{list}{\textendash}{%
     \resume@listsetup
     \setlength{\topsep}{1\p@}%
     \setlength{\itemsep}{0.5\p@}%
     \setlength{\leftmargin}{1.2em}%
     \setlength{\labelwidth}{0.75em}%
     \setlength{\labelsep}{0.45em}%
   }}
  {\end{list}}

% -- bold run-in lead-in, replaces moderncv's two-column \cvitem -----------
\newcommand{\resumeLead}[1]{\par\addvspace{2\p@}\textbf{#1:}\space}

\makeatother

\endinput
