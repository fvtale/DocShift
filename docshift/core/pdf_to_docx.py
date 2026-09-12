"""PDF to DOCX, on pdf2docx.

The only module that imports pdf2docx. What it adds around it:

- A password-protected or empty-after-repair PDF fails with a sentence a person
  can act on, not a MuPDF traceback.
- Pages pdf2docx could not convert are reported. Left to its own defaults it
  logs the failure and carries on, and the DOCX comes out a page short with
  nothing on screen to say so.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from docshift.core.convert import ConversionError, Outcome

if TYPE_CHECKING:
    from pdf2docx import Converter


def run(source: Path, target: Path) -> Outcome:
    """Convert the PDF at `source` into a DOCX at `target`."""
    engine = _load_engine()
    try:
        converter = engine(str(source))
    except Exception as exc:
        # MuPDF's own errors: a damaged file, or one that only starts like a PDF.
        raise ConversionError(
            f"{source.name} could not be opened. It may be damaged. ({exc})"
        ) from exc

    try:
        return _convert(converter, source, target)
    finally:
        converter.close()


def _convert(converter: Converter, source: Path, target: Path) -> Outcome:
    document = converter.fitz_doc
    if document.needs_pass:
        raise ConversionError(
            f"{source.name} is password-protected. Remove the password and try again."
        )
    if document.page_count == 0:
        # What MuPDF makes of a file that starts like a PDF and is not one: it
        # "repairs" it into a document with nothing in it.
        raise ConversionError(f"{source.name} has no pages. It may be damaged.")

    try:
        converter.convert(str(target))
    except Exception as exc:
        raise ConversionError(_describe_failure(converter, source, exc)) from exc

    return Outcome(pages=document.page_count, skipped=_skipped_pages(converter))


def _skipped_pages(converter: Converter) -> tuple[int, ...]:
    """Pages pdf2docx was asked to convert and could not, numbered from 1.

    A page that parsed is `finalized`. Under pdf2docx's default of
    ignore_page_error=True, one that failed is logged and left out, and
    convert() returns as though nothing had happened.
    """
    return tuple(
        page.id + 1 for page in converter.pages if not page.skip_parsing and not page.finalized
    )


def _describe_failure(converter: Converter, source: Path, exc: Exception) -> str:
    wanted = [page for page in converter.pages if not page.skip_parsing]
    if wanted and not any(page.finalized for page in wanted):
        # Every page failed and pdf2docx has nothing to write. Its own message,
        # "No parsed pages. Please parse page first.", means nothing to a user.
        if len(wanted) == 1:
            return f"{source.name} has one page, and it could not be converted."
        return f"None of the {len(wanted)} pages in {source.name} could be converted."
    return f"{source.name} could not be converted. ({exc})"


def _load_engine() -> type[Converter]:
    """Import pdf2docx's Converter without letting the import rewire the program.

    Importing pdf2docx has two side effects, both undone here:

    - It calls logging.basicConfig(level=INFO), taking over the root logger of
      whatever program imported it, so every conversion would print progress.
    - PyMuPDF prints straight to stdout -- including a deprecation warning that
      pdf2docx sets off by importing it under its old name, `fitz`. The command
      line prints the path of each file on stdout, which has to stay clean, so
      PyMuPDF's messages go to the "pymupdf" logger at INFO. --verbose shows them.
    """
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    try:
        import pymupdf

        pymupdf.set_messages(pylogging_name="pymupdf", pylogging_level=logging.INFO)
        from pdf2docx import Converter
    except ImportError as exc:
        raise ConversionError(
            f"The conversion engine is not installed ({exc.name} is missing). "
            f"Run: pip install -r requirements.txt"
        ) from exc
    except SystemExit as exc:
        # pdf2docx calls sys.exit() when it dislikes the installed PyMuPDF. That
        # should end one conversion, not the whole program.
        raise ConversionError(f"The conversion engine could not start: {exc}") from None
    finally:
        root.handlers[:] = handlers
        root.setLevel(level)
    return Converter
