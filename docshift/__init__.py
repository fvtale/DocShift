"""DocShift: free document conversion that runs on your own machine.

PDF to Word, Word to PDF. Nothing is uploaded anywhere: the file is read and
the converted one written locally.

  core/     the conversion engines -- no Qt, so they run without a display
  gui/      the desktop window, the only package that imports Qt
  cli.py    the same conversions from a terminal, and what CI drives

`python -m docshift` opens the window; `python -m docshift report.pdf` converts
from the terminal.
"""

__version__ = "0.2.0"
