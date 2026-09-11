# DocShift

Free PDF to DOCX conversion, on your own machine, with a minimalist black and
red interface. Nothing is uploaded, nothing is metered, and it stays free.

| | |
| --- | --- |
| **Converts** | PDF → DOCX |
| **Runs on** | Windows, as a single `.exe` — or anywhere Python and Qt run |
| **Costs** | Nothing, forever. The source is [public domain](LICENSE) |

---

## Why

Converting between standard file formats is a solved problem that keeps being
sold back to people — per page, per month, or in exchange for uploading their
documents to someone else's server. DocShift does it locally, for free.

---

## Get it

### Windows, no Python needed

CI builds `DocShift.exe` on every push to `main`.

1. Open the [CI runs](https://github.com/fvtale/DocShift/actions/workflows/ci.yml)
   and click the latest green run on `main`.
2. Under **Artifacts**, download **DocShift-windows** (GitHub asks you to sign
   in first) and unzip it.
3. Run `DocShift.exe`.

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

Pick a PDF, optionally pick a folder, and press **Convert to DOCX**.

- The DOCX is saved beside the PDF unless you choose a folder.
- **An existing DOCX is never overwritten.** The new one is saved as
  `report (1).docx`, then `report (2).docx`, and so on.
- A file that is missing, damaged, password-protected, or not really a PDF is
  refused with a message saying which. Nothing half-written is left behind.
- If a page cannot be converted, the rest still are — and DocShift tells you
  which page is missing, rather than quietly handing you a shorter document.
- The window stays responsive while it works. Closing it mid-conversion lets
  the conversion finish first.
- Dropping a PDF onto `DocShift.exe`, or **Open with → DocShift**, opens the
  window with that file filled in.

### Command line

```bash
python -m docshift report.pdf                    # report.docx, beside it
python -m docshift *.pdf --output converted/     # many at once, into a folder
python -m docshift report.pdf --overwrite        # replace report.docx
```

Each DOCX written is printed on its own line, and nothing else goes to stdout.
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

The result is `dist\DocShift.exe`. The last line proves it converts a real PDF.

---

## Layout

```
docshift/
  __main__.py      python -m docshift: the window, or the command line
  cli.py           the command line
  core/
    convert.py     PDF to DOCX; the only file that imports pdf2docx
  gui/
    app.py         starts Qt
    window.py      the window, and the thread that keeps it responsive
    style.py       the black and red theme
    docshift.ico   the icon
packaging/
  docshift.spec    PyInstaller recipe for DocShift.exe
  build_exe.bat    builds it on a Windows machine
  smoke_test.py    converts a real PDF with a build, as CI does
  make_icon.py     redraws docshift.ico
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

---

Nothing here is built or run on the author's machine — there is no local
Python toolchain. **CI is the only thing that tests DocShift, and the only
thing that builds DocShift.exe.** A red CI run is a broken download.
