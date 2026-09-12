# Third-party software in DocShift.exe

The DocShift source code in this repository is dedicated to the public domain
under [CC0 1.0](LICENSE).

`DocShift.exe` is more than that source. It bundles the Python runtime and the
libraries below, each under its own licence. Because PyMuPDF is licensed under
the GNU Affero General Public License v3, **DocShift.exe as a whole is
distributed under the AGPL v3.** That keeps it free: anyone who receives the
.exe may use, study, share and change it, and the complete source is public --
this repository, plus the projects linked below.

| Component | What DocShift uses it for | Licence | Source |
| --- | --- | --- | --- |
| Python | the runtime | PSF-2.0 | https://github.com/python/cpython |
| OpenSSL | hashing, via Python | Apache-2.0 | https://github.com/openssl/openssl |
| PySide6 (Qt) | the window | LGPL-3.0 | https://code.qt.io/cgit/pyside/pyside-setup.git/ |
| shiboken6 | Qt's Python bindings | LGPL-3.0 | https://code.qt.io/cgit/pyside/pyside-setup.git/ |
| pdf2docx | converting PDF to DOCX | MIT | https://github.com/ArtifexSoftware/pdf2docx |
| PyMuPDF (MuPDF) | reading PDFs, and drawing the pages of one converted from Word | AGPL-3.0 | https://github.com/pymupdf/PyMuPDF |
| python-docx | reading and writing Word files | MIT | https://github.com/python-openxml/python-docx |
| lxml | XML for python-docx | BSD-3-Clause | https://github.com/lxml/lxml |
| NumPy | image analysis | BSD-3-Clause | https://github.com/numpy/numpy |
| OpenCV | finding drawings and tables | Apache-2.0 | https://github.com/opencv/opencv-python |
| fontTools | font metrics | MIT | https://github.com/fonttools/fonttools |
| Python Fire | pdf2docx's own command line | Apache-2.0 | https://github.com/google/python-fire |
| termcolor | pdf2docx's log colours | MIT | https://github.com/termcolor/termcolor |
| typing_extensions | python-docx | PSF-2.0 | https://github.com/python/typing_extensions |
| PyInstaller bootloader | starting the .exe | GPL-2.0 with the bootloader exception | https://github.com/pyinstaller/pyinstaller |

Each project's own repository carries its full licence text, and the notices of
anything it bundles in turn.

Qt is used under the LGPL v3, which lets anyone replace it with their own
build. To do that, build DocShift.exe from this repository against your copy of
PySide6: see "Building the .exe yourself" in [README.md](README.md).

This page is a courtesy summary of the licences involved, not legal advice.
