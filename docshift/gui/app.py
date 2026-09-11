"""Starts Qt and shows the window."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from docshift import __version__
from docshift.gui.window import MainWindow

# Beside this file in the source tree, and in the same place inside
# DocShift.exe: packaging/docshift.spec puts it there.
ICON = Path(__file__).with_name("docshift.ico")


def run(pdf: str | None = None) -> int:
    """Open the window, with `pdf` filled in if given, and block until it closes."""
    # Only the program name goes to Qt. A file path passed in by Explorer is
    # DocShift's to handle, not a Qt command-line option.
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("DocShift")
    app.setApplicationVersion(__version__)
    app.setWindowIcon(QIcon(str(ICON)))

    window = MainWindow()
    if pdf:
        window.set_pdf(pdf)
    window.show()
    return app.exec()
