"""`python -m docshift`, and the entry point of DocShift.exe.

No arguments opens the window. Arguments are a command line, and Qt is never
imported for one -- conversions run on machines with no display at all.
"""

from __future__ import annotations

import multiprocessing
import sys


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or opened_from_explorer(argv):
        from docshift.gui.app import run

        return run(argv[0] if argv else None)

    from docshift.cli import main as convert

    return convert(argv)


def opened_from_explorer(argv: list[str]) -> bool:
    """True when DocShift.exe was started by dropping files on it, or Open with.

    Explorer passes the files' paths and nothing else, to a process that has no
    console. Taken as a command line, that would convert them invisibly -- so
    the window opens with the first one filled in instead.

    Without a console, then, only an option makes it a command line. That is
    how CI drives the .exe: it always passes --output.
    """
    return sys.stdout is None and not any(arg.startswith("-") for arg in argv)


if __name__ == "__main__":
    # A frozen Windows app re-runs itself as any child process it starts,
    # unless this is called first. pdf2docx has a multi-processing mode; it is
    # off, but one stray Pool would otherwise open a second window.
    multiprocessing.freeze_support()
    sys.exit(main())
