"""DocShift: free PDF to DOCX conversion that runs on your own machine.

Nothing is uploaded anywhere. The PDF is read and the DOCX is written locally.

  core/     the conversion engine -- no Qt, so it runs without a display
  gui/      the desktop window, the only package that imports Qt
  cli.py    the same conversion from a terminal, and what CI drives

`python -m docshift` opens the window; `python -m docshift report.pdf` converts
from the terminal.
"""

__version__ = "0.1.0"
