"""What DocShift converts, and the rules every conversion keeps.

Two directions, one entry point. `convert()` reads the file, works out what it
is, and hands it to the engine that goes the other way:

    PDF  -> DOCX    core/pdf_to_docx.py, on pdf2docx
    DOCX -> PDF     core/docx_to_pdf.py, on MuPDF's story engine

This module is what the two have in common, and where the promises a desktop
tool has to keep are made:

- The file's first bytes decide what it is, not its name. A PDF saved as
  "scan.docx" still converts as a PDF, and a Word file renamed "cv.pdf" is
  refused rather than turned into nonsense.
- An existing file is never replaced unless the caller asks. The new one takes
  the next free name instead: "report (1).docx".
- A conversion that fails partway leaves nothing behind. Output is written to a
  temporary file beside its destination and renamed into place only once it is
  complete.
- Whatever an engine could not carry over -- a page it failed to parse, a
  header it cannot draw -- comes back with the result instead of going quiet.
"""

from __future__ import annotations

import importlib
import os
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

# The PDF header may sit anywhere in the first kilobyte. Acrobat accepts that,
# so MuPDF does, and so does this check.
_HEADER_WINDOW = 1024

# The binary .doc format Word wrote until 2007, which DocShift cannot read.
_OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


class ConversionError(RuntimeError):
    """A conversion could not be done. The message is written for the user."""


@dataclass(frozen=True)
class Conversion:
    """One direction DocShift converts in."""

    name: str  # "PDF to DOCX", as the button and the status line say it
    target_suffix: str
    engine: str  # the module whose run() does the work

    def run(self, source: Path, target: Path) -> Outcome:
        # Imported on use, not at startup: pdf2docx brings NumPy and OpenCV with
        # it, and converting one way should never load the other way's engine.
        return importlib.import_module(self.engine).run(source, target)


PDF_TO_DOCX = Conversion("PDF to DOCX", ".docx", "docshift.core.pdf_to_docx")
DOCX_TO_PDF = Conversion("DOCX to PDF", ".pdf", "docshift.core.docx_to_pdf")


@dataclass(frozen=True)
class Outcome:
    """What an engine did with one file."""

    pages: int
    # Pages the engine could not convert, numbered from 1. They are missing
    # from the output.
    skipped: tuple[int, ...] = ()
    # Anything else the user should know, as whole sentences: what was in the
    # document that could not be carried across.
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class Result:
    """A finished conversion."""

    output: Path
    pages: int
    conversion: Conversion
    skipped: tuple[int, ...] = ()
    notes: tuple[str, ...] = field(default=())

    @property
    def complete(self) -> bool:
        return not self.skipped


def convert(
    source: str | os.PathLike[str],
    output_dir: str | os.PathLike[str] | None = None,
    *,
    overwrite: bool = False,
) -> Result:
    """Convert one file into the other format, named after it.

    The result goes into `output_dir`, which is created if it does not exist,
    or beside the original when no folder is given.
    """
    path, conversion = check_input(source)
    folder = _prepare_folder(Path(output_dir) if output_dir else path.parent)

    partial = _temporary_file(folder, conversion.target_suffix)
    try:
        outcome = conversion.run(path, partial)
        target = output_path(path, folder, conversion.target_suffix, overwrite=overwrite)
        _rename(partial, target)
    finally:
        # Already gone once the rename succeeded. Otherwise it is a failed
        # conversion's half-written file, and nobody asked for that.
        _discard(partial)

    return Result(
        output=target,
        pages=outcome.pages,
        conversion=conversion,
        skipped=outcome.skipped,
        notes=outcome.notes,
    )


def check_input(source: str | os.PathLike[str]) -> tuple[Path, Conversion]:
    """Return the file and the direction it converts in.

    Reads the first bytes rather than trusting the extension: a PDF saved as
    "scan.PDF" or just "scan" is still a PDF, and a Word file renamed to
    "cv.pdf" is not one.
    """
    path = Path(source).expanduser()
    if not path.exists():
        raise ConversionError(f"Cannot find {path}.")
    if path.is_dir():
        raise ConversionError(f"{path} is a folder, not a document.")
    try:
        with path.open("rb") as handle:
            head = handle.read(_HEADER_WINDOW)
    except OSError as exc:
        raise ConversionError(f"{path.name} could not be read: {exc.strerror or exc}") from exc

    if b"%PDF-" in head:
        return path, PDF_TO_DOCX
    if head[:2] == b"PK" and _is_word_document(path):
        return path, DOCX_TO_PDF
    if head.startswith(_OLE_MAGIC):
        raise ConversionError(
            f"{path.name} is in Word's older .doc format. Open it, save it as "
            f".docx, and try again."
        )
    raise ConversionError(f"{path.name} is not a PDF or a Word document.")


def output_path(source: Path, folder: Path, suffix: str, *, overwrite: bool = False) -> Path:
    """Where the conversion of `source` goes.

    `folder/report.docx`, unless that exists and `overwrite` is off, in which
    case the first free one of `report (1).docx`, `report (2).docx`, ...
    """
    target = folder / f"{source.stem}{suffix}"
    # Replacing is never allowed to land on the original. That only happens to a
    # file saved under the other format's extension, which is exactly the case
    # where it would destroy the only copy.
    if overwrite and not _same_file(target, source):
        return target
    number = 0
    while target.exists():
        number += 1
        target = folder / f"{source.stem} ({number}){suffix}"
    return target


def describe_pages(numbers: tuple[int, ...] | list[int]) -> str:
    """Page numbers as a phrase: "page 3", "pages 3 and 7", "pages 1, 2 and 5"."""
    if len(numbers) == 1:
        return f"page {numbers[0]}"
    listed = ", ".join(str(number) for number in numbers[:-1])
    return f"pages {listed} and {numbers[-1]}"


def _is_word_document(path: Path) -> bool:
    """True for a .docx: a zip with Word's main document part inside.

    Every Office file is a zip, so the zip alone proves nothing -- a spreadsheet
    or a slide deck gets this far.
    """
    try:
        with zipfile.ZipFile(path) as archive:
            return "word/document.xml" in archive.namelist()
    except (zipfile.BadZipFile, OSError):
        return False


def _prepare_folder(folder: Path) -> Path:
    folder = folder.expanduser()
    if folder.exists() and not folder.is_dir():
        raise ConversionError(f"{folder} is a file, not a folder.")
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ConversionError(f"Cannot create the folder {folder}: {exc.strerror or exc}") from exc
    return folder


def _temporary_file(folder: Path, suffix: str) -> Path:
    """Create an empty file in `folder` for the conversion to be written into.

    Made here rather than with tempfile.mkstemp, which creates files only their
    owner can read -- and the rename would pass that on to the finished file.
    """
    partial = folder / f".docshift-{uuid.uuid4().hex[:12]}{suffix}.part"
    try:
        partial.open("xb").close()
    except OSError as exc:
        raise ConversionError(f"Cannot write to {folder}: {exc.strerror or exc}") from exc
    return partial


def _rename(partial: Path, target: Path) -> None:
    replacing = target.exists()
    try:
        os.replace(partial, target)
    except OSError as exc:
        if replacing:
            # On Windows this is almost always the old file, open in Word.
            raise ConversionError(
                f"{target.name} could not be replaced. If it is open in another "
                f"program, close it and try again."
            ) from exc
        raise ConversionError(f"{target.name} could not be saved: {exc.strerror or exc}") from exc


def _same_file(a: Path, b: Path) -> bool:
    return a.exists() and b.exists() and os.path.samefile(a, b)


def _discard(partial: Path) -> None:
    """Remove the half-written file, if it can be removed.

    An engine that failed may still hold its own output open, and Windows will
    not unlink an open file. The error already on its way up is the one that
    matters; a leftover temporary file is not worth replacing it with.
    """
    try:
        partial.unlink(missing_ok=True)
    except OSError:
        pass
