"""DocShift's browser side: one conversion, bytes in and bytes out.

Pyodide runs this in a Web Worker on datarail.org/docshift. It calls the same
engines as the desktop app -- docshift.core, unchanged -- on a file system that
exists only in the browser tab's memory. The file is never uploaded: there is
nowhere for it to go.
"""

from __future__ import annotations

import logging
import re
import shutil
from collections.abc import Callable
from pathlib import Path

from docshift.core.convert import ConversionError, convert, describe_pages

WORK = Path("/tmp/docshift")

_ANSI = re.compile(r"\x1b\[[0-9;]*m")
_PAGE = re.compile(r"^\((\d+)/(\d+)\) Page \d+$")


class _Progress(logging.Handler):
    """Turns pdf2docx's progress log into short lines for the page's status.

    pdf2docx logs its four stages, then one line per page twice: once while
    reading the layout, once while writing the DOCX. The stage tells the two
    apart.
    """

    STAGES = {
        "[1/4]": "Opening the PDF",
        "[2/4]": "Reading the layout",
        "[3/4]": "Reading pages",
        "[4/4]": "Writing the DOCX",
    }

    def __init__(self, report: Callable[[str], None]) -> None:
        super().__init__(logging.INFO)
        self.report = report
        self.writing = False

    def emit(self, record: logging.LogRecord) -> None:
        message = _ANSI.sub("", record.getMessage()).strip()
        for marker, text in self.STAGES.items():
            if message.startswith(marker):
                self.writing = marker == "[4/4]"
                self.report(text)
                return
        page = _PAGE.match(message)
        if page:
            verb = "Writing" if self.writing else "Reading"
            self.report(f"{verb} page {page[1]} of {page[2]}")


def convert_bytes(name: str, data: bytes, report: Callable[[str], None]) -> dict:
    """Convert one file held in memory. Returns what the page needs to show."""
    if hasattr(data, "to_bytes"):
        # A JavaScript Uint8Array, which is how the page hands the file over.
        data = data.to_bytes()

    # One conversion at a time, and nothing from the last one kept around: a tab
    # converting its tenth file should not still be holding the other nine.
    shutil.rmtree(WORK, ignore_errors=True)
    (WORK / "in").mkdir(parents=True)
    source = WORK / "in" / _file_name(name)
    source.write_bytes(data)

    root = logging.getLogger()
    progress = _Progress(report)
    level = root.level
    root.addHandler(progress)
    root.setLevel(logging.INFO)
    try:
        result = convert(source, WORK / "out")
    except ConversionError as exc:
        return {"ok": False, "message": str(exc)}
    finally:
        root.removeHandler(progress)
        root.setLevel(level)

    return {
        "ok": True,
        "name": result.output.name,
        "data": result.output.read_bytes(),
        "kind": result.conversion.target_suffix.lstrip("."),
        "direction": result.conversion.name,
        "pages": result.pages,
        "missing": describe_pages(result.skipped) if result.skipped else "",
        "missing_count": len(result.skipped),
        "notes": list(result.notes),
    }


def _file_name(name: str) -> str:
    """The upload's own name, made safe to use as a path.

    A browser gives just the file name, never a path, but nothing stops it
    containing a slash or being empty.
    """
    cleaned = name.replace("/", "_").replace("\\", "_").replace("\x00", "").strip()
    return cleaned if cleaned not in ("", ".", "..") else "document"
