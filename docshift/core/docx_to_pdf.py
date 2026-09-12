"""DOCX to PDF, without Word.

Word is the only program that lays out a .docx exactly as Word does, and it is
neither free nor present in a browser tab. So DocShift reads the document with
python-docx and draws it with MuPDF's story engine: an HTML rendering of what
the document holds, on paper the size the document asks for.

Carried across: headings, bold, italic, underline, strikethrough, superscript
and subscript, font size, colour and family, paragraph alignment, indentation
and spacing, bulleted and numbered lists including nesting, tables with merged
cells, pictures, links, explicit page breaks, and the page size and margins of
the document's first section.

Not carried across: headers and footers, footnotes, columns, text boxes, drawn
shapes, charts, comments and tracked changes. A document leaning on those still
converts, but comes out simpler than it went in -- and says which of them it
dropped, rather than letting the reader discover it.
"""

from __future__ import annotations

import html
import logging
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

from docshift.core.convert import ConversionError, Outcome

try:
    import pymupdf
    from docx import Document
    from docx.oxml.ns import qn
    from docx.table import Table
    from docx.text.hyperlink import Hyperlink
    from docx.text.paragraph import Paragraph
except ImportError as exc:  # The module is imported only to convert a DOCX.
    raise ConversionError(
        f"The conversion engine is not installed ({exc.name} is missing). "
        f"Run: pip install -r requirements.txt"
    ) from exc

# Word's own defaults, so a document that styles nothing still looks like it did
# in Word: 11pt sans, a little space after each paragraph, blue-grey headings.
BASE_CSS = """
body { font-family: sans-serif; font-size: 11pt; line-height: 1.15; }
p { margin: 0 0 8pt 0; }
h1, h2, h3, h4, h5, h6 { color: #2f5496; font-weight: normal; margin: 14pt 0 4pt 0; }
h1 { font-size: 16pt; }
h2 { font-size: 13pt; }
h3 { font-size: 12pt; }
h4, h5, h6 { font-size: 11pt; font-style: italic; }
ul, ol { margin: 0 0 8pt 0; padding-left: 24pt; }
li { margin: 0 0 2pt 0; }
/* Word fits a table to the text width unless told otherwise, and a table left
   to size itself to its contents comes out a narrow column of wrapped words. */
table { border-collapse: collapse; margin: 0 0 8pt 0; width: 100%; }
td { padding: 3pt 5pt; vertical-align: top; }
table.ruled td { border: 0.75pt solid #808080; }
a { color: #0563c1; }
img { max-width: 100%; }
"""

# MuPDF draws from its own font set, so Word's font names become the family the
# document was reaching for. Anything unlisted is treated as sans, which is what
# Calibri, Arial, Segoe UI, Verdana and Tahoma all are.
_SERIF = {
    "times new roman", "times", "cambria", "georgia", "garamond", "book antiqua",
    "palatino linotype", "constantia", "century schoolbook", "bookman old style",
    "minion pro", "baskerville", "didot",
}
_MONO = {
    "consolas", "courier new", "courier", "lucida console", "cascadia code",
    "cascadia mono", "monaco", "menlo", "dejavu sans mono",
}

# Pictures MuPDF can draw. Word also embeds EMF and WMF, which it cannot.
_PICTURES = {"image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif"}

_ALIGNMENT = {0: "left", 1: "center", 2: "right", 3: "justify"}

# 914400 EMU to the inch, 72 points to the inch.
_EMU_PER_POINT = 12700

# A runaway layout -- something that will not fit, placed forever -- is stopped
# rather than filling the disk.
_MAX_PAGES = 5000


@dataclass(frozen=True)
class _Paper:
    """A page and its margins, in points."""

    width: float
    height: float
    left: float
    top: float
    right: float
    bottom: float


_LETTER = _Paper(612.0, 792.0, 72.0, 72.0, 72.0, 72.0)


def run(source: Path, target: Path) -> Outcome:
    """Render the DOCX at `source` into a PDF at `target`."""
    _quieten_mupdf()
    try:
        document = Document(str(source))
    except Exception as exc:
        raise ConversionError(
            f"{source.name} could not be opened. It may be damaged. ({exc})"
        ) from exc

    # Pictures reach the story engine through a folder it is given to read.
    with tempfile.TemporaryDirectory(prefix="docshift-docx-") as folder:
        pictures = Path(folder)
        builder = _Builder(document, pictures)
        chunks = builder.build()
        pages = _write(chunks, _paper(document), pictures, source, target)

    return Outcome(pages=pages, notes=builder.notes(source))


def _write(chunks: list[str], paper: _Paper, pictures: Path, source: Path, target: Path) -> int:
    """Lay the HTML out onto pages and write the PDF. Returns the page count."""
    media = pymupdf.Rect(0, 0, paper.width, paper.height)
    where = pymupdf.Rect(
        paper.left, paper.top, paper.width - paper.right, paper.height - paper.bottom
    )
    writer = pymupdf.DocumentWriter(str(target))
    pages = 0
    device = None
    try:
        for chunk in chunks:
            story = pymupdf.Story(html=chunk, user_css=BASE_CSS, archive=pymupdf.Archive(pictures))
            more, stuck = True, 0
            while more:
                device = writer.begin_page(media)
                more, filled = story.place(where)
                story.draw(device)
                writer.end_page()
                # MuPDF keeps the PDF open through the page's device, and
                # closing the writer does not take it back. On Windows that
                # leaves a file nothing can rename or delete.
                device = None
                pages += 1
                # Nothing fitted on a whole page twice running: something in the
                # document is wider or taller than the paper and never will fit.
                stuck = stuck + 1 if pymupdf.Rect(filled).is_empty else 0
                if stuck >= 2 or pages > _MAX_PAGES:
                    raise ConversionError(
                        f"{source.name} has something on it too large to fit the page, "
                        f"so it could not be laid out."
                    )
    except ConversionError:
        raise
    except Exception as exc:
        raise ConversionError(f"{source.name} could not be converted. ({exc})") from exc
    finally:
        device = None
        writer.close()
    return pages


def _paper(document: Document) -> _Paper:
    """The first section's paper and margins. US Letter if it says nothing."""
    try:
        section = document.sections[0]
    except (IndexError, KeyError, ValueError):
        return _LETTER

    def points(value: object, fallback: float) -> float:
        return float(value.pt) if value is not None else fallback

    paper = _Paper(
        width=points(section.page_width, _LETTER.width),
        height=points(section.page_height, _LETTER.height),
        left=points(section.left_margin, _LETTER.left),
        top=points(section.top_margin, _LETTER.top),
        right=points(section.right_margin, _LETTER.right),
        bottom=points(section.bottom_margin, _LETTER.bottom),
    )
    # Margins wider than the paper would leave nowhere to draw.
    if (
        paper.width - paper.left - paper.right < 72
        or paper.height - paper.top - paper.bottom < 72
    ):
        return _LETTER
    return paper


class _Builder:
    """Turns a Word document into HTML the story engine can lay out.

    The output is a list of HTML chunks, one per explicit page break: the story
    engine paginates what it is given but has no page break of its own, so each
    chunk is laid out separately and starts on a fresh page.
    """

    def __init__(self, document: Document, pictures: Path) -> None:
        self.document = document
        self.pictures = pictures
        self.parts: list[str] = []
        self.done: list[str] = []
        self.lists: list[tuple[str, int]] = []  # open <ul>/<ol> and their level
        self.drawn = 0
        self.undrawable = 0
        # The cell elements already drawn. They are held by the set on purpose:
        # lxml hands out a proxy per element and reuses the memory of collected
        # ones, so id() is not an identity that lasts -- keeping the elements
        # alive is what makes "have I drawn this one?" answerable.
        self.rendered_cells: set = set()
        self._break_after = False

    def build(self) -> list[str]:
        for block in _blocks(self.document.element.body, self.document):
            if isinstance(block, Table):
                self._close_lists()
                self.parts.append(self._table(block))
            else:
                self._paragraph(block)
        self._close_lists()
        self.done.append("".join(self.parts))
        return [chunk for chunk in self.done if chunk.strip()] or ["<p>&#160;</p>"]

    def notes(self, source: Path) -> tuple[str, ...]:
        notes = []
        if _has_header_or_footer(self.document):
            notes.append("Headers and footers are not carried over.")
        if _has_footnotes(source):
            notes.append("Footnotes are not carried over.")
        if self.undrawable:
            what = "picture is" if self.undrawable == 1 else "pictures are"
            notes.append(
                f"{self.undrawable} {what} in a format that cannot be drawn "
                f"(Word's EMF or WMF) and were left out."
            )
        return tuple(notes)

    # -- blocks ---------------------------------------------------------------

    def _paragraph(self, paragraph: Paragraph) -> None:
        if _breaks_before(paragraph):
            self._page_break()

        self._break_after = False
        inline = self._inline(paragraph)  # may set _break_after, via a page break run
        listing = _list_of(paragraph, self.document)

        if listing is None:
            self._close_lists()
            self.parts.append(self._wrap(paragraph, inline))
        else:
            tag, level = listing
            self._open_list(tag, level)
            self.parts.append(f"<li>{inline or '&#160;'}</li>")

        if self._break_after:
            self._page_break()

    def _wrap(self, paragraph: Paragraph, inline: str) -> str:
        tag = _heading_tag(paragraph)
        rules = _paragraph_css(paragraph)
        attribute = f' style="{rules}"' if rules else ""
        # Word's empty paragraphs are deliberate spacing. Keep them.
        return f"<{tag}{attribute}>{inline or '&#160;'}</{tag}>"

    def _page_break(self) -> None:
        self._close_lists()
        self.done.append("".join(self.parts))
        self.parts = []

    def _open_list(self, tag: str, level: int) -> None:
        while self.lists and self.lists[-1][1] > level:
            self.parts.append(f"</{self.lists.pop()[0]}>")
        if self.lists and self.lists[-1][1] == level:
            if self.lists[-1][0] == tag:
                return
            self.parts.append(f"</{self.lists.pop()[0]}>")
        self.parts.append(f"<{tag}>")
        self.lists.append((tag, level))

    def _close_lists(self) -> None:
        while self.lists:
            self.parts.append(f"</{self.lists.pop()[0]}>")

    # -- tables ---------------------------------------------------------------

    def _table(self, table: Table) -> str:
        rows = []
        for row in table.rows:
            cells: list[str] = []
            previous, span = None, 1
            for cell in row.cells:
                if previous is not None and cell._tc is previous._tc:
                    span += 1  # one cell reported once per grid column it spans
                    continue
                if previous is not None:
                    cells.append(self._cell(previous, span))
                previous, span = cell, 1
            if previous is not None:
                cells.append(self._cell(previous, span))
            rows.append(f"<tr>{''.join(cells)}</tr>")
        ruled = " class=\"ruled\"" if _is_ruled(table) else ""
        return f"<table{ruled}>{''.join(rows)}</table>"

    def _cell(self, cell: object, span: int) -> str:
        attribute = f' colspan="{span}"' if span > 1 else ""
        # A vertically merged cell is reported again by every row it covers.
        # Draw it once, and leave the rest of the column empty.
        if cell._tc in self.rendered_cells:
            return f"<td{attribute}>&#160;</td>"
        self.rendered_cells.add(cell._tc)

        inner = []
        for block in _blocks(cell._tc, cell):
            if isinstance(block, Table):
                inner.append(self._table(block))
            else:
                inner.append(self._wrap(block, self._inline(block)))
        return f"<td{attribute}>{''.join(inner) or '&#160;'}</td>"

    # -- inline ---------------------------------------------------------------

    def _inline(self, paragraph: Paragraph) -> str:
        pieces = []
        for item in paragraph.iter_inner_content():
            if isinstance(item, Hyperlink):
                text = "".join(self._run(run) for run in item.runs)
                address = item.address
                pieces.append(
                    f'<a href="{html.escape(address, quote=True)}">{text}</a>'
                    if address and text
                    else text
                )
            else:
                pieces.append(self._run(item))
        return "".join(pieces)

    def _run(self, run: object) -> str:
        pieces = []
        for child in run._r.iterchildren():
            tag = child.tag
            if tag == qn("w:t"):
                pieces.append(html.escape(child.text or ""))
            elif tag == qn("w:br"):
                if child.get(qn("w:type")) == "page":
                    self._break_after = True
                else:
                    pieces.append("<br>")
            elif tag == qn("w:tab"):
                pieces.append("&#160;&#160;&#160;&#160;")
            elif tag == qn("w:noBreakHyphen"):
                pieces.append("&#8209;")
            elif tag in (qn("w:drawing"), qn("w:pict")):
                pieces.append(self._picture(child))
        text = "".join(pieces)
        return _decorate(run, text) if text else ""

    def _picture(self, element: object) -> str:
        blips = element.findall(".//" + qn("a:blip"))
        embed = blips[0].get(qn("r:embed")) if blips else None
        if not embed:
            return ""
        try:
            part = self.document.part.related_parts[embed]
        except KeyError:
            return ""

        suffix = _PICTURES.get(part.content_type)
        if suffix is None:
            # EMF and WMF: MuPDF cannot draw them, and a broken <img> would take
            # the rest of the page down with it.
            self.undrawable += 1
            return ""

        self.drawn += 1
        name = f"image{self.drawn}{suffix}"
        (self.pictures / name).write_bytes(part.blob)
        return f'<img src="{name}"{_picture_size(element)}>'


# -- reading the document -----------------------------------------------------


def _blocks(parent_element: object, parent: object):
    """Paragraphs and tables in the order they appear.

    python-docx keeps .paragraphs and .tables in separate lists, each in its own
    order: reading them one after the other would move every table in the
    document to the end.
    """
    for child in parent_element.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, parent)
        elif child.tag == qn("w:tbl"):
            yield Table(child, parent)


def _heading_tag(paragraph: Paragraph) -> str:
    name = (paragraph.style.name or "") if paragraph.style is not None else ""
    lowered = name.strip().lower()
    if lowered.startswith("heading "):
        level = lowered[len("heading ") :].strip()
        if level.isdigit():
            return f"h{min(int(level), 6)}"
    if lowered == "title":
        return "h1"
    return "p"


def _paragraph_css(paragraph: Paragraph) -> str:
    rules = []
    alignment = paragraph.alignment
    if alignment is None and paragraph.style is not None:
        alignment = paragraph.style.paragraph_format.alignment
    if alignment is not None and int(alignment) in _ALIGNMENT:
        rules.append(f"text-align: {_ALIGNMENT[int(alignment)]}")

    spacing = paragraph.paragraph_format
    if spacing.left_indent and spacing.left_indent.pt > 0:
        rules.append(f"margin-left: {spacing.left_indent.pt:.0f}pt")
    if spacing.right_indent and spacing.right_indent.pt > 0:
        rules.append(f"margin-right: {spacing.right_indent.pt:.0f}pt")
    if spacing.first_line_indent and spacing.first_line_indent.pt > 0:
        rules.append(f"text-indent: {spacing.first_line_indent.pt:.0f}pt")
    if spacing.space_before is not None:
        rules.append(f"margin-top: {spacing.space_before.pt:.0f}pt")
    if spacing.space_after is not None:
        rules.append(f"margin-bottom: {spacing.space_after.pt:.0f}pt")
    return "; ".join(rules)


def _decorate(run: object, text: str) -> str:
    font = run.font
    if font.strike:
        text = f"<s>{text}</s>"
    if font.underline:
        text = f"<u>{text}</u>"
    if font.italic:
        text = f"<i>{text}</i>"
    if font.bold:
        text = f"<b>{text}</b>"
    if font.superscript:
        text = f"<sup>{text}</sup>"
    elif font.subscript:
        text = f"<sub>{text}</sub>"

    rules = []
    if font.size is not None:
        rules.append(f"font-size: {font.size.pt:.1f}pt")
    family = _family(font.name)
    if family:
        rules.append(f"font-family: {family}")
    colour = _colour(font)
    if colour:
        rules.append(f"color: {colour}")
    return f'<span style="{"; ".join(rules)}">{text}</span>' if rules else text


def _family(name: str | None) -> str | None:
    if not name:
        return None
    lowered = name.strip().lower()
    if lowered in _MONO:
        return "monospace"
    if lowered in _SERIF:
        return "serif"
    return "sans-serif"


def _colour(font: object) -> str | None:
    try:
        rgb = font.color.rgb  # None for a theme colour, which has no value here
    except (AttributeError, TypeError, ValueError):
        return None
    if rgb is None:
        return None
    value = str(rgb)
    return f"#{value}" if len(value) == 6 else None


def _picture_size(element: object) -> str:
    extent = element.find(".//" + qn("wp:extent"))
    if extent is None:
        return ""
    try:
        width = int(extent.get("cx")) / _EMU_PER_POINT
        height = int(extent.get("cy")) / _EMU_PER_POINT
    except (TypeError, ValueError):
        return ""
    if width <= 0 or height <= 0:
        return ""
    return f' style="width: {width:.0f}pt; height: {height:.0f}pt"'


def _breaks_before(paragraph: Paragraph) -> bool:
    properties = paragraph._p.pPr
    return properties is not None and properties.find(qn("w:pageBreakBefore")) is not None


def _list_of(paragraph: Paragraph, document: Document) -> tuple[str, int] | None:
    """The list tag and nesting level for a paragraph, or None if it is not one.

    Word puts the numbering on the paragraph itself when someone makes a list
    from the ribbon, and leaves it in the style when the document was written
    against styles such as "List Bullet 2". Both are lists to whoever reads the
    document, so both are lists here.
    """
    style_name = ""
    if paragraph.style is not None:
        style_name = (paragraph.style.name or "").strip().lower()

    properties = paragraph._p.pPr
    numbering = properties.numPr if properties is not None else None
    if numbering is not None and numbering.numId is not None and numbering.numId.val in (None, 0):
        return None  # Word cancels an inherited list with numId 0.

    if numbering is None:
        numbering = _style_numbering(paragraph)
        if numbering is None and not _is_list_style(style_name):
            return None

    level = 0
    if numbering is not None and numbering.ilvl is not None and numbering.ilvl.val:
        level = int(numbering.ilvl.val)
    elif style_name:
        level = _style_level(style_name)

    num_id = numbering.numId.val if numbering is not None and numbering.numId is not None else None
    if num_id:
        ordered = _is_ordered(document, num_id, level)
    else:
        ordered = "number" in style_name
    return ("ol" if ordered else "ul"), level


def _style_numbering(paragraph: Paragraph):
    """The numbering a paragraph's style carries, if any."""
    if paragraph.style is None:
        return None
    properties = getattr(paragraph.style.element, "pPr", None)
    return getattr(properties, "numPr", None) if properties is not None else None


def _is_list_style(name: str) -> bool:
    # Not "list paragraph": Word gives that to list items, but also to anything
    # else someone indented, and an indented sentence is not a bullet.
    return name.startswith("list bullet") or name.startswith("list number")


def _style_level(name: str) -> int:
    """"List Bullet 3" is the third level, which is level 2 counting from zero."""
    tail = name.rsplit(" ", 1)[-1]
    return int(tail) - 1 if tail.isdigit() and int(tail) > 0 else 0


def _is_ordered(document: Document, num_id: int, level: int) -> bool:
    """Whether a list is numbered rather than bulleted, per numbering.xml."""
    try:
        numbering = document.part.numbering_part.element
    except (AttributeError, KeyError, NotImplementedError, ValueError):
        return False
    try:
        abstract = numbering.xpath(f'w:num[@w:numId="{num_id}"]/w:abstractNumId/@w:val')
        if not abstract:
            return False
        formats = numbering.xpath(
            f'w:abstractNum[@w:abstractNumId="{abstract[0]}"]'
            f'/w:lvl[@w:ilvl="{level}"]/w:numFmt/@w:val'
        )
    except Exception:
        return False
    return bool(formats) and formats[0] not in ("bullet", "none")


def _is_ruled(table: Table) -> bool:
    """Whether to draw cell borders.

    Word keeps borders on the table or in the style it points at, and python-docx
    does not resolve the style. An explicit "no borders" is honoured; everything
    else gets light rules, which is what all but deliberately invisible layout
    tables have.
    """
    properties = table._tbl.tblPr
    if properties is None:
        return True
    borders = properties.find(qn("w:tblBorders"))
    if borders is None:
        return True
    values = {child.get(qn("w:val")) for child in borders}
    return not (values and values <= {"none", "nil"})


def _has_header_or_footer(document: Document) -> bool:
    for section in document.sections:
        for area in (section.header, section.footer):
            if area.tables or any(paragraph.text.strip() for paragraph in area.paragraphs):
                return True
    return False


def _has_footnotes(source: Path) -> bool:
    """True when the document has footnotes of its own.

    Word writes two footnotes into every document that ever had the part -- the
    separator and its continuation -- so their presence alone means nothing.
    """
    try:
        with zipfile.ZipFile(source) as archive:
            if "word/footnotes.xml" not in archive.namelist():
                return False
            return archive.read("word/footnotes.xml").count(b"<w:footnote ") > 2
    except (zipfile.BadZipFile, KeyError, OSError):
        return False


def _quieten_mupdf() -> None:
    """Send MuPDF's messages to logging instead of stdout.

    The command line prints the path of each file it writes on stdout, and a
    MuPDF warning landing in the middle of that would be read as one.
    """
    pymupdf.set_messages(pylogging_name="pymupdf", pylogging_level=logging.INFO)
