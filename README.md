# DocShift

Free document conversion, on your own machine, with a minimalist black and red
interface. Nothing is uploaded, nothing is metered, and it stays free.

| | |
| --- | --- |
| **Converts** | PDF → Word, and Word → PDF |
| **Runs on** | Windows, as a single `.exe`; any browser, at [datarail.org/docshift](https://datarail.org/docshift); anywhere Python and Qt run |
| **Costs** | Nothing, forever. The source is [public domain](LICENSE) |

---

## Why

Converting between standard file formats is a solved problem that keeps being
sold back to people — per page, per month, or in exchange for uploading their
documents to someone else's server. DocShift does it locally, for free.

---

## Get it

### In your browser, nothing to install

[**datarail.org/docshift**](https://datarail.org/docshift) converts without
installing anything. The page loads the same converter into your browser and
runs it there, so the PDF is never uploaded — there is no server to upload it
to. The first conversion downloads about 38 MB of Python and PDF libraries,
once.

### Windows, no Python needed

**[Download DocShift-windows.zip](https://github.com/fvtale/DocShift/releases/latest/download/DocShift-windows.zip)**,
unzip it, and run `DocShift.exe`. No installer, no Python, nothing to sign up
for.

Every release is built and smoke-tested by CI from a tag; see
[Releasing](#releasing). For the build of a commit that has no release yet, open
the [CI runs](https://github.com/fvtale/DocShift/actions/workflows/ci.yml), click
a green run, and take the **DocShift-windows** artifact (GitHub asks you to sign
in for those).

The .exe is not code-signed, so Windows SmartScreen warns about an unknown
publisher the first time. **More info → Run anyway.** It takes a few seconds to
open: a one-file app unpacks itself each time it starts.

### From source

Python 3.11 or newer:

```bash
pip install -r requirements.txt
python -m docshift
```

---

## Using it

Pick a file, optionally pick a folder, and press **Convert**. A PDF becomes a
Word document; a Word document becomes a PDF. Which way it goes is read from
the file itself, not from its name, and the button says which before you press
it.

- The converted file is saved beside the original unless you choose a folder.
- **An existing file is never overwritten.** The new one is saved as
  `report (1).docx`, then `report (2).docx`, and so on.
- A file that is missing, damaged, password-protected, or neither a PDF nor a
  Word document is refused with a message saying which. Nothing half-written is
  left behind.
- If a page cannot be converted, the rest still are — and DocShift tells you
  which page is missing, rather than quietly handing you a shorter document.
- **Word to PDF is drawn by DocShift, not by Word.** Headings, bold and italic,
  fonts, sizes and colours, alignment, lists, tables, pictures, links, page
  breaks and the document's paper size all carry over. Headers, footers,
  footnotes, columns, text boxes and tracked changes do not — and DocShift says
  which of them it dropped instead of letting you find out later.
- The window stays responsive while it works. Closing it mid-conversion lets
  the conversion finish first.
- Dropping a PDF or Word file onto `DocShift.exe`, or **Open with →
  DocShift**, opens the window with that file filled in.

### Command line

```bash
python -m docshift report.pdf                    # report.docx, beside it
python -m docshift letter.docx                   # letter.pdf, beside it
python -m docshift *.pdf *.docx -o converted/    # many at once, into a folder
python -m docshift report.pdf --overwrite        # replace report.docx
```

Each file written is printed on its own line, and nothing else goes to stdout.
Exit code 0 when every file converted, 1 when any failed, 2 for a usage error.
`--verbose` shows the conversion engine's progress.

`DocShift.exe` takes the same options. Because it has no console, it treats
file paths on their own as a drop onto its icon and opens the window; add any
option, such as `--output`, to convert without one.

---

## Building the .exe yourself

On Windows with Python 3.11 or newer, double-click `packaging\build_exe.bat`,
or run:

```bash
pip install -r requirements.txt pyinstaller
pyinstaller --noconfirm --clean packaging/docshift.spec
python packaging/smoke_test.py dist/DocShift.exe
```

The result is `dist\DocShift.exe`. The last line proves it converts a real PDF
 and a real Word document.

---

## Releasing

A tag publishes the Windows build where anyone can download it, at a URL that
never changes:

```bash
git tag v0.2.0
git push origin v0.2.0
```

`.github/workflows/release.yml` then runs the tests, builds the .exe, makes it
convert a real PDF and a real Word document, and attaches
`DocShift-windows.zip` — the .exe, `LICENSE` and `THIRD-PARTY-NOTICES.md` — to
a GitHub release. Nothing is published that has not converted something first.

---

## The browser version

[datarail.org/docshift](https://datarail.org/docshift) is this same engine
compiled to WebAssembly. The page loads [Pyodide](https://pyodide.org) into a
Web Worker and runs `docshift/core` there unchanged, alongside
Pyodide's own builds of PyMuPDF, OpenCV and NumPy. The two pure-Python pieces
it still needs — pdf2docx and python-docx — are served with the page, pinned
and checked against the SHA-256 that PyPI publishes for them.

```bash
cd web
npm install
npm run build     # stages dist/web, the folder that gets deployed
npm test          # converts a PDF and a Word file through it, in Node
npm run serve     # http://localhost:8765/docshift/, with the live site's assets
```

CI does the first two on every push and uploads `dist/web` as the
**DocShift-web** artifact. To publish it, copy that folder to
`public/docshift/` in [datarail-site](https://github.com/fvtale/datarail-site),
whose own workflow uploads it to the webspace.

---

## Layout

```
docshift/
  __main__.py      python -m docshift: the window, or the command line
  cli.py           the command line
  core/
    convert.py     what converts to what, and the rules both directions keep
    pdf_to_docx.py PDF to DOCX; the only file that imports pdf2docx
    docx_to_pdf.py DOCX to PDF, drawn without Word
  gui/
    app.py         starts Qt
    window.py      the window, and the thread that keeps it responsive
    style.py       the black and red theme
    docshift.ico   the icon
packaging/
  docshift.spec    PyInstaller recipe for DocShift.exe
  build_exe.bat    builds it on a Windows machine
  smoke_test.py    converts real files with a build, both ways, as CI does
  make_icon.py     redraws docshift.ico
web/
  index.html       the page at datarail.org/docshift
  app.js           choosing a file, the progress line, the download
  worker.js        the Web Worker that Python runs in
  engine.js        boots Pyodide; shared by the page and by CI's test
  docshift_web.py  the browser's side of one conversion
  build.js         stages dist/web, the folder that gets deployed
  smoke.js         converts real files through the built page, in Node
  serve.js         npm run serve, to preview the built page
tests/
```

Nothing under `core/` imports Qt, so the command line and its tests run on
machines with no display.

---

## Licence

The DocShift source is dedicated to the public domain under
[CC0 1.0](LICENSE). Use it for anything; no permission needed.

`DocShift.exe` bundles third-party libraries under their own licences. One of
them — PyMuPDF, which reads the PDF — is AGPL v3, so the .exe as a whole is
distributed under the AGPL v3. It stays free to use, share and change. See
[THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).

The browser version loads that same PyMuPDF into your browser, so the same
applies there; the page lists everything it loads and under what licence.

---

Nothing here is built or run on the author's machine — there is no local
Python toolchain. **CI is the only thing that tests DocShift, and the only
thing that builds DocShift.exe and the page behind datarail.org/docshift.**
A red CI run is a broken download.
