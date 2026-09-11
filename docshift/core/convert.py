"""PDF to DOCX, and everything that can go wrong on the way.

pdf2docx does the converting. This is the only module that imports it, and it
exists to give the conversion the edges a desktop tool needs:

- A file that is missing, not a PDF, damaged or password-protected fails with
  a sentence a person can act on, not a MuPDF traceback.
- An existing DOCX is never replaced unless the caller asks. The new one takes
  the next free name instead: "report (1).docx".
- A conversion that fails partway leaves nothing behind. The DOCX is written to
  a temporary file beside its destination and renamed into place only once it
  is complete.
- Pages pdf2docx could not convert are reported. Left to its defaults it logs
  the failure and carries on, and the DOCX comes out a page short with nothing
  on screen to say so.
"""

from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pdf2docx import Converter

# The PDF header may sit anywhere in the first kilobyte. Acrobat accepts that,
# so MuPDF does, and so does this check.
_HEADER_WINDOW = 1024


class ConversionError(RuntimeError):
    """A conversion could not be done. The message is written for the user."""


@dataclass(frozen=True)
class Result:
    """A finished conversion."""

    output: Path
    pages: int
    # Pages pdf2docx could not convert, numbered from 1. They are missing from
    # the DOCX. Empty when the conversion is complete.
    skipped: tuple[int, ...] = ()

    @property
    def complete(self) -> bool:
        return not self.skipped


def pdf_to_docx(
    source: str | os.PathLike[str],
    output_dir: str | os.PathLike[str] | None = None,
    *,
    overwrite: bool = False,
) -> Result:
    """Convert one PDF to a DOCX named after it.

    The DOCX goes into `output_dir`, which is created if it does not exist, or
    beside the PDF when no folder is given.
    """
    pdf = check_pdf(source)
    folder = _prepare_folder(Path(output_dir) if output_dir else pdf.parent)
    engine = _load_engine()

    try:
        converter = engine(str(pdf))
    except Exception as exc:
        # MuPDF's own errors: a damaged file, or one that only starts like a PDF.
        raise ConversionError(f"{pdf.name} could not be opened. It may be damaged. ({exc})") from exc

    try:
        return _convert(converter, pdf, folder, overwrite)
    finally:
        converter.close()


def check_pdf(source: str | os.PathLike[str]) -> Path:
    """Return `source` as a Path, or raise ConversionError if it is not a PDF.

    Reads the file's first bytes rather than trusting its extension: a PDF saved
    as "scan.PDF" or just "scan" is still a PDF, and a Word file renamed to
    "cv.pdf" is not.
    """
    pdf = Path(source).expanduser()
    if not pdf.exists():
        raise ConversionError(f"Cannot find {pdf}.")
    if pdf.is_dir():
        raise ConversionError(f"{pdf} is a folder, not a PDF.")
    try:
        with pdf.open("rb") as handle:
            head = handle.read(_HEADER_WINDOW)
    except OSError as exc:
        raise ConversionError(f"{pdf.name} could not be read: {exc.strerror or exc}") from exc
    if b"%PDF-" not in head:
        raise ConversionError(f"{pdf.name} is not a PDF.")
    return pdf


def output_path(pdf: Path, folder: Path, *, overwrite: bool = False) -> Path:
    """Where the DOCX for `pdf` goes.

    `folder/report.docx`, unless that exists and `overwrite` is off, in which
    case the first free one of `report (1).docx`, `report (2).docx`, ...
    """
    target = folder / f"{pdf.stem}.docx"
    # Replacing is never allowed to land on the PDF itself. That can only happen
    # to a PDF saved with a .docx extension -- and it would destroy the only copy.
    if overwrite and not _same_file(target, pdf):
        return target
    number = 0
    while target.exists():
        number += 1
        target = folder / f"{pdf.stem} ({number}).docx"
    return target


def describe_pages(numbers: tuple[int, ...] | list[int]) -> str:
    """Page numbers as a phrase: "page 3", "pages 3 and 7", "pages 1, 2 and 5"."""
    if len(numbers) == 1:
        return f"page {numbers[0]}"
    listed = ", ".join(str(number) for number in numbers[:-1])
    return f"pages {listed} and {numbers[-1]}"


def _convert(converter: Converter, pdf: Path, folder: Path, overwrite: bool) -> Result:
    document = converter.fitz_doc
    if document.needs_pass:
        raise ConversionError(
            f"{pdf.name} is password-protected. Remove the password and try again."
        )
    if document.page_count == 0:
        # What MuPDF makes of a file that starts like a PDF and is not one: it
        # "repairs" it into a document with nothing in it.
        raise ConversionError(f"{pdf.name} has no pages. It may be damaged.")

    partial = _temporary_file(folder)
    try:
        try:
            converter.convert(str(partial))
        except Exception as exc:
            raise ConversionError(_describe_failure(converter, pdf, exc)) from exc
        target = output_path(pdf, folder, overwrite=overwrite)
        replacing = target.exists()
        try:
            os.replace(partial, target)
        except OSError as exc:
            if replacing:
                # On Windows this is almost always the old DOCX, open in Word.
                raise ConversionError(
                    f"{target.name} could not be replaced. If it is open in another "
                    f"program, close it and try again."
                ) from exc
            raise ConversionError(f"{target.name} could not be saved: {exc.strerror or exc}") from exc
    finally:
        # Already gone when the rename succeeded. Otherwise it is a failed
        # conversion's half-written file, and nobody asked for it.
        partial.unlink(missing_ok=True)

    return Result(output=target, pages=document.page_count, skipped=_skipped_pages(converter))


def _prepare_folder(folder: Path) -> Path:
    folder = folder.expanduser()
    if folder.exists() and not folder.is_dir():
        raise ConversionError(f"{folder} is a file, not a folder.")
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ConversionError(f"Cannot create the folder {folder}: {exc.strerror or exc}") from exc
    return folder


def _temporary_file(folder: Path) -> Path:
    """Create an empty file in `folder` for the DOCX to be written into.

    Made here rather than with tempfile.mkstemp, which creates files only their
    owner can read -- and the rename would pass that on to the finished DOCX.
    """
    partial = folder / f".docshift-{uuid.uuid4().hex[:12]}.docx.part"
    try:
        partial.open("xb").close()
    except OSError as exc:
        raise ConversionError(f"Cannot write to {folder}: {exc.strerror or exc}") from exc
    return partial


def _same_file(a: Path, b: Path) -> bool:
    return a.exists() and b.exists() and os.path.samefile(a, b)


def _skipped_pages(converter: Converter) -> tuple[int, ...]:
    """Pages pdf2docx was asked to convert and could not, numbered from 1.

    A page that parsed is `finalized`. Under pdf2docx's default of
    ignore_page_error=True, one that failed is logged and left out, and
    convert() returns as though nothing had happened.
    """
    return tuple(
        page.id + 1 for page in converter.pages if not page.skip_parsing and not page.finalized
    )


def _describe_failure(converter: Converter, pdf: Path, exc: Exception) -> str:
    wanted = [page for page in converter.pages if not page.skip_parsing]
    if wanted and not any(page.finalized for page in wanted):
        # Every page failed and pdf2docx has nothing to write. Its own message,
        # "No parsed pages. Please parse page first.", means nothing to a user.
        if len(wanted) == 1:
            return f"{pdf.name} has one page, and it could not be converted."
        return f"None of the {len(wanted)} pages in {pdf.name} could be converted."
    return f"{pdf.name} could not be converted. ({exc})"


def _load_engine() -> type[Converter]:
    """Import pdf2docx's Converter without letting the import rewire the program.

    Importing pdf2docx has two side effects, both undone here:

    - It calls logging.basicConfig(level=INFO), taking over the root logger of
      whatever program imported it, so every conversion would print progress.
    - PyMuPDF prints straight to stdout -- including a deprecation warning that
      pdf2docx sets off by importing it under its old name, `fitz`. The command
      line prints the path of each DOCX on stdout, which has to stay clean, so
      PyMuPDF's messages go to the "pymupdf" logger at INFO. --verbose shows them.

    It happens on first use rather than at import time: pdf2docx brings NumPy,
    OpenCV and MuPDF with it, and the window should not wait on them to appear.
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
