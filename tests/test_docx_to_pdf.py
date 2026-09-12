"""Tests for DOCX to PDF.

Word is not here to lay the document out, so DocShift draws it itself. These
check that what the document holds arrives in the PDF -- its text, formatting,
lists, table, picture, page breaks and paper size -- and that whatever cannot
be drawn is owned up to instead of quietly going missing.
"""

from __future__ import annotations

import zipfile

import pytest

from docshift.core.convert import ConversionError, convert


class TestConversion:
    def test_text_survives(self, make_docx, read_pdf, tmp_path):
        source = make_docx(tmp_path / "letter.docx", ["Dear Ms Matusik", "Yours sincerely"])
        result = convert(source)

        assert result.output == tmp_path / "letter.pdf"
        assert result.conversion.name == "DOCX to PDF"
        assert result.pages == 1
        text = "".join(read_pdf(result.output))
        assert "Dear Ms Matusik" in text
        assert "Yours sincerely" in text

    def test_the_output_is_a_real_pdf(self, make_docx, tmp_path):
        result = convert(make_docx(tmp_path / "letter.docx"))
        assert result.output.read_bytes().startswith(b"%PDF-")

    def test_leaves_nothing_else_behind(self, make_docx, tmp_path):
        convert(make_docx(tmp_path / "letter.docx"))
        assert sorted(path.name for path in tmp_path.iterdir()) == ["letter.docx", "letter.pdf"]

    def test_everything_in_a_rich_document(self, rich_docx, read_pdf, tmp_path):
        result = convert(rich_docx(tmp_path / "report.docx"), tmp_path / "out")
        pages = read_pdf(result.output)

        assert result.pages == 2, "the explicit page break should start a second page"
        assert "This is on the second page." in pages[1]
        # Line breaks are the layout's business, so compare on the words alone.
        first = " ".join(pages[0].split())
        for expected in (
            "Quarterly Report",
            "Centred and red",
            "bold",
            "italic",
            "First bullet",
            "Nested bullet",
            "Step one",
            "Region",
            "New York",
            "one merged cell",
        ):
            assert expected in first, expected
        assert "•" in first, "the bullet list lost its bullets"
        assert "○" in first, "the nested level should be drawn differently"
        assert "1." in first, "the numbered list lost its numbering"

    def test_formatting_arrives(self, rich_docx, tmp_path):
        import pymupdf

        result = convert(rich_docx(tmp_path / "report.docx"), tmp_path / "out")
        with pymupdf.open(result.output) as document:
            page = document[0]
            assert page.get_images(), "the picture is missing"
            assert page.get_drawings(), "the table's rules are missing"
            spans = [
                span
                for block in page.get_text("dict")["blocks"]
                for line in block.get("lines", [])
                for span in line["spans"]
            ]

        centred = next(span for span in spans if "Centred" in span["text"])
        assert centred["color"] == 0xCC0033, "the colour was lost"
        assert round(centred["size"]) == 16, "the font size was lost"
        assert centred["bbox"][0] > 150, "the centred paragraph is not centred"
        assert any("bold" in s["text"] and "Bold" in s["font"] for s in spans), "bold was lost"
        assert any("italic" in s["text"] and "Italic" in s["font"] for s in spans), "italic lost"

    def test_the_paper_is_the_document_s_own(self, tmp_path):
        import docx
        import pymupdf
        from docx.shared import Mm

        document = docx.Document()
        section = document.sections[0]
        section.page_width, section.page_height = Mm(210), Mm(297)  # A4, not Letter
        document.add_paragraph("Printed on A4.")
        source = tmp_path / "a4.docx"
        document.save(str(source))

        with pymupdf.open(convert(source).output) as converted:
            assert round(converted[0].rect.width) == 595
            assert round(converted[0].rect.height) == 842


class TestSaysWhatItCannotCarry:
    def test_a_header_is_admitted_to(self, rich_docx, tmp_path):
        result = convert(rich_docx(tmp_path / "report.docx"), tmp_path / "out")
        assert "Headers and footers are not carried over." in result.notes

    def test_a_plain_document_has_nothing_to_admit(self, make_docx, tmp_path):
        assert convert(make_docx(tmp_path / "plain.docx")).notes == ()


class TestNeverOverwrites:
    def test_an_existing_pdf_is_kept(self, make_docx, tmp_path):
        source = make_docx(tmp_path / "letter.docx")
        (tmp_path / "letter.pdf").write_bytes(b"%PDF- the one already there")

        result = convert(source)

        assert result.output == tmp_path / "letter (1).pdf"
        assert (tmp_path / "letter.pdf").read_bytes() == b"%PDF- the one already there"


class TestRefusals:
    """Every refusal says what is wrong, in a sentence, and writes nothing."""

    def refuse(self, source) -> str:
        with pytest.raises(ConversionError) as caught:
            convert(source)
        return str(caught.value)

    def test_the_older_doc_format(self, tmp_path):
        old = tmp_path / "memo.doc"
        old.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + bytes(200))
        assert "older .doc format" in self.refuse(old)

    def test_another_kind_of_office_file(self, tmp_path):
        # A real zip, and not a Word document: every Office file is a zip, so
        # the zip alone must not be enough to be taken for one.
        book = tmp_path / "budget.xlsx"
        with zipfile.ZipFile(book, "w") as archive:
            archive.writestr("xl/workbook.xml", "<workbook/>")
        assert self.refuse(book) == "budget.xlsx is not a PDF or a Word document."

    def test_a_damaged_document(self, tmp_path):
        broken = tmp_path / "broken.docx"
        with zipfile.ZipFile(broken, "w") as archive:
            archive.writestr("word/document.xml", "<gibberish/>")
        assert "broken.docx could not be" in self.refuse(broken)
        assert sorted(path.name for path in tmp_path.iterdir()) == ["broken.docx"]
