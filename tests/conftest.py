"""Fixtures shared by the tests.

Qt runs on its offscreen platform, so the window tests need no display: not on
a CI runner, and not on a Windows machine with the screen locked.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def make_pdf():
    """Write a small PDF with one line of text per page.

    Drawn with PyMuPDF, which pdf2docx cannot run without, so the tests need
    nothing the app does not already install.
    """
    import pymupdf

    def make(path, pages=("A page converted by DocShift",), password=None):
        document = pymupdf.open()
        for text in pages:
            document.new_page().insert_text((72, 72), text, fontsize=14)
        if password:
            document.save(
                str(path),
                encryption=pymupdf.PDF_ENCRYPT_AES_256,
                user_pw=password,
                owner_pw=password + "-owner",
            )
        else:
            document.save(str(path))
        document.close()
        return path

    return make


@pytest.fixture
def read_docx():
    """All the paragraph text in a DOCX, one paragraph per line."""
    import docx

    def read(path) -> str:
        return "\n".join(paragraph.text for paragraph in docx.Document(str(path)).paragraphs)

    return read


@pytest.fixture
def break_pages(monkeypatch):
    """Make pdf2docx fail on the given pages, numbered from 1.

    The same failure a page with layout pdf2docx cannot parse produces, without
    needing a PDF that reliably breaks it.
    """
    from docshift.core.convert import _load_engine

    # Import pdf2docx the way the app does, so its import side effects are
    # contained here too.
    _load_engine()
    from pdf2docx.page.Page import Page

    original = Page.parse

    def break_on(*numbers):
        def parse(page, **settings):
            if page.id + 1 in numbers:
                raise RuntimeError(f"simulated layout failure on page {page.id + 1}")
            return original(page, **settings)

        monkeypatch.setattr(Page, "parse", parse)

    return break_on


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    # The tests close windows on purpose. That must not end the application.
    app.setQuitOnLastWindowClosed(False)
    return app
