"""The command line: `python -m docshift report.pdf`.

It converts exactly as the window does -- same engines, same refusal to
overwrite -- and it is how CI proves a real file becomes a real conversion,
both from source and from the finished DocShift.exe.

stdout carries one line per file written: its path, and nothing else, so a
script can use it. Everything meant for a person goes to stderr.

Exit codes: 0 when every file converted, 1 when any failed, 2 for a usage error.
"""

from __future__ import annotations

import argparse
import logging
import sys

from docshift import __version__
from docshift.core.convert import ConversionError, convert, describe_pages


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="docshift",
        description=(
            "Convert PDF files to Word, and Word files to PDF. Each file's own "
            "contents decide which way it goes. With no arguments, opens the "
            "DocShift window."
        ),
    )
    parser.add_argument("files", nargs="+", metavar="FILE", help="PDF or Word files to convert")
    parser.add_argument(
        "-o",
        "--output",
        metavar="FOLDER",
        help="folder for the converted files (default: beside each original)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help='replace an existing file instead of saving as "name (1).docx"',
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="show the conversion engine's progress",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(message)s",
    )

    failures = 0
    for source in args.files:
        try:
            result = convert(source, args.output, overwrite=args.overwrite)
        except ConversionError as exc:
            failures += 1
            print(f"docshift: {exc}", file=sys.stderr)
            continue

        print(result.output)
        if not result.complete:
            print(
                f"docshift: {describe_pages(result.skipped)} of {source} could not be "
                f"converted and {'is' if len(result.skipped) == 1 else 'are'} missing "
                f"from {result.output.name}",
                file=sys.stderr,
            )
        for note in result.notes:
            print(f"docshift: {note}", file=sys.stderr)
    return 1 if failures else 0
