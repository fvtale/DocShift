"""Tests for the conversion engine.

These are the tests that matter most in this repo. The window and the command
line are thin; this is where a mistake overwrites someone's document or hands
them one with a page missing.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from docshift.core.convert import (
    ConversionError,
    describe_pages,
    output_path,
    pdf_to_docx,
)

ROOT = Path(__file__).resolve().parent.parent


class TestConversion:
    def test_text_survives(self, make_pdf, read_docx, tmp_path):
        pdf = make_pdf(tmp_path / "report.pdf", ["Quarterly figures"])
        result = pdf_to_docx(pdf)
        assert result.output == tmp_path / "report.docx"
        assert "Quarterly figures" in read_docx(result.output)
        assert result.pages == 1
        assert result.complete

    def test_every_page_survives(self, make_pdf, read_docx, tmp_path):
        pdf = make_pdf(tmp_path / "long.pdf", ["First page", "Second page", "Third page"])
        result = pdf_to_docx(pdf)
        text = read_docx(result.output)
        for line in ("First page", "Second page", "Third page"):
            assert line in text, line
        assert result.pages == 3

    def test_writes_into_the_chosen_folder_creating_it(self, make_pdf, tmp_path):
        pdf = make_pdf(tmp_path / "report.pdf")
        result = pdf_to_docx(pdf, tmp_path / "converted" / "2026")
        assert result.output == tmp_path / "converted" / "2026" / "report.docx"
        assert result.output.exists()

    def test_leaves_nothing_else_behind(self, make_pdf, tmp_path):
        pdf = make_pdf(tmp_path / "report.pdf")
        pdf_to_docx(pdf)
        assert sorted(path.name for path in tmp_path.iterdir()) == ["report.docx", "report.pdf"]

    def test_the_extension_does_not_matter(self, make_pdf, tmp_path):
        pdf = make_pdf(tmp_path / "SCAN.PDF")
        assert pdf_to_docx(pdf).output == tmp_path / "SCAN.docx"


class TestNeverOverwrites:
    def test_an_existing_docx_is_kept(self, make_pdf, tmp_path):
        pdf = make_pdf(tmp_path / "report.pdf")
        (tmp_path / "report.docx").write_bytes(b"the edited copy")
        result = pdf_to_docx(pdf)
        assert result.output == tmp_path / "report (1).docx"
        assert (tmp_path / "report.docx").read_bytes() == b"the edited copy"

    def test_numbering_continues(self, tmp_path):
        for name in ("report.docx", "report (1).docx", "report (2).docx"):
            (tmp_path / name).touch()
        assert output_path(tmp_path / "report.pdf", tmp_path) == tmp_path / "report (3).docx"

    def test_overwrite_replaces_when_asked(self, make_pdf, tmp_path):
        pdf = make_pdf(tmp_path / "report.pdf")
        (tmp_path / "report.docx").write_bytes(b"old")
        result = pdf_to_docx(pdf, overwrite=True)
        assert result.output == tmp_path / "report.docx"
        # A DOCX is a zip file.
        assert result.output.read_bytes()[:2] == b"PK"

    def test_overwrite_never_lands_on_the_pdf_itself(self, make_pdf, tmp_path):
        # A PDF that was saved with a .docx extension. Replacing "notes.docx"
        # would destroy the only copy of it.
        pdf = make_pdf(tmp_path / "notes.docx")
        result = pdf_to_docx(pdf, overwrite=True)
        assert result.output == tmp_path / "notes (1).docx"
        assert pdf.read_bytes().startswith(b"%PDF-")


class TestRefusals:
    """Every refusal says what is wrong, in a sentence, and writes nothing."""

    def refuse(self, source, *, folder=None) -> str:
        with pytest.raises(ConversionError) as caught:
            pdf_to_docx(source, folder)
        return str(caught.value)

    def test_missing_file(self, tmp_path):
        assert "Cannot find" in self.refuse(tmp_path / "nowhere.pdf")

    def test_a_folder(self, tmp_path):
        assert "is a folder, not a PDF" in self.refuse(tmp_path)

    def test_not_a_pdf(self, tmp_path):
        fake = tmp_path / "cv.pdf"
        fake.write_bytes(b"PK\x03\x04 a Word document, renamed")
        assert self.refuse(fake) == "cv.pdf is not a PDF."

    def test_empty_file(self, tmp_path):
        empty = tmp_path / "empty.pdf"
        empty.touch()
        assert self.refuse(empty) == "empty.pdf is not a PDF."

    def test_password_protected(self, make_pdf, tmp_path):
        pdf = make_pdf(tmp_path / "locked.pdf", password="secret")
        assert "password-protected" in self.refuse(pdf)
        assert sorted(path.name for path in tmp_path.iterdir()) == ["locked.pdf"]

    def test_damaged(self, tmp_path):
        broken = tmp_path / "broken.pdf"
        broken.write_bytes(b"%PDF-1.7\n" + bytes(range(256)) * 40)
        self.refuse(broken)
        assert sorted(path.name for path in tmp_path.iterdir()) == ["broken.pdf"]

    def test_output_folder_that_is_a_file(self, make_pdf, tmp_path):
        pdf = make_pdf(tmp_path / "report.pdf")
        (tmp_path / "taken").touch()
        assert "is a file, not a folder" in self.refuse(pdf, folder=tmp_path / "taken")


class TestMissingPages:
    """pdf2docx drops a page it cannot parse and carries on. DocShift says so."""

    def test_a_failed_page_is_reported(self, make_pdf, read_docx, break_pages, tmp_path):
        pdf = make_pdf(tmp_path / "report.pdf", ["Page one", "Page two", "Page three"])
        break_pages(2)
        result = pdf_to_docx(pdf)
        assert result.skipped == (2,)
        assert not result.complete
        text = read_docx(result.output)
        assert "Page one" in text and "Page three" in text
        assert "Page two" not in text

    def test_every_page_failing_is_an_error(self, make_pdf, break_pages, tmp_path):
        pdf = make_pdf(tmp_path / "report.pdf", ["Page one", "Page two"])
        break_pages(1, 2)
        with pytest.raises(ConversionError) as caught:
            pdf_to_docx(pdf)
        assert str(caught.value) == "None of the 2 pages in report.pdf could be converted."
        assert sorted(path.name for path in tmp_path.iterdir()) == ["report.pdf"]

    def test_describing_pages(self):
        assert describe_pages((3,)) == "page 3"
        assert describe_pages((3, 7)) == "pages 3 and 7"
        assert describe_pages((1, 2, 5)) == "pages 1, 2 and 5"


def test_the_engine_import_leaves_logging_and_stdout_alone():
    """pdf2docx configures the root logger when imported, and PyMuPDF prints a
    deprecation warning to stdout. Neither may leak into the program.

    Run in a fresh interpreter: in this one, pdf2docx is long since imported.
    """
    code = (
        "import logging\n"
        "from docshift.core.convert import _load_engine\n"
        "_load_engine()\n"
        "root = logging.getLogger()\n"
        "assert not root.handlers, root.handlers\n"
        "assert root.level == logging.WARNING, root.level\n"
    )
    done = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, cwd=ROOT, timeout=120
    )
    assert done.returncode == 0, done.stderr
    assert done.stdout == ""
