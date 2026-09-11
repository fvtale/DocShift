"""The DocShift window: one PDF in, one DOCX out.

The conversion runs on a worker thread. pdf2docx takes seconds per page on a
long document, and the first version ran it on the UI thread, where Windows
marks the window "Not Responding" and offers to kill it.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal, Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from docshift.core.convert import ConversionError, Result, describe_pages, pdf_to_docx
from docshift.gui.style import APP_STYLE


class ConversionThread(QThread):
    """Runs one conversion and reports how it ended.

    Exactly one of `succeeded` or `failed` is emitted, then QThread's own
    `finished`. The window acts only on `finished`, so by the time it re-enables
    anything the thread is done -- a second conversion cannot start on top of
    the first, and the app never quits under a running thread, which aborts it.
    """

    succeeded = Signal(object)  # a Result
    failed = Signal(str)

    def __init__(self, pdf: str, output_dir: str | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.pdf = pdf
        self.output_dir = output_dir

    def run(self) -> None:
        try:
            result = pdf_to_docx(self.pdf, self.output_dir)
        except ConversionError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            # A bug, not a bad PDF -- but it still has to reach the user. An
            # exception escaping run() ends the thread without a word, and the
            # window would sit on "Converting..." forever.
            self.failed.emit(f"Something went wrong inside DocShift: {exc!r}")
        else:
            self.succeeded.emit(result)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("DocShift")
        # Width only. The layout knows the height it needs; a fixed minimum
        # height of 360 let the window be dragged shorter than that, squashing
        # the text boxes until their text was cut in half.
        self.setMinimumWidth(640)
        self.setStyleSheet(APP_STYLE)
        self._thread: ConversionThread | None = None
        self._outcome: Result | str | None = None
        self._close_when_done = False
        self._build_ui()

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)

        outer = QVBoxLayout(root)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.setSpacing(0)

        card = QFrame()
        card.setObjectName("Card")
        outer.addWidget(card)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(26, 26, 26, 26)
        layout.setSpacing(18)

        title = QLabel("PDF to DOCX")
        title.setObjectName("Title")
        subtitle = QLabel("Minimal conversion, dark interface, fast workflow.")
        subtitle.setObjectName("Subtitle")

        layout.addWidget(title)
        layout.addWidget(subtitle)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)

        self.pdf_edit = QLineEdit()
        self.pdf_edit.setPlaceholderText("Select a PDF file...")
        self.pdf_btn = QPushButton("Browse")
        self.pdf_btn.clicked.connect(self.pick_pdf)

        self.out_edit = QLineEdit()
        self.out_edit.setPlaceholderText("Same folder as the PDF")
        self.out_btn = QPushButton()
        self.out_btn.setToolTip("Choose output folder")
        self.out_btn.setText("📁")
        self.out_btn.setFixedWidth(52)
        self.out_btn.clicked.connect(self.pick_output_folder)

        grid.addWidget(QLabel("Input PDF"), 0, 0)
        grid.addWidget(self.pdf_edit, 1, 0)
        grid.addWidget(self.pdf_btn, 1, 1)
        grid.addWidget(QLabel("Output Folder"), 2, 0)
        grid.addWidget(self.out_edit, 3, 0)
        grid.addWidget(self.out_btn, 3, 1)

        layout.addLayout(grid)

        bottom = QHBoxLayout()
        self.status = QLabel("Ready.")
        self.status.setObjectName("Status")
        self.convert_btn = QPushButton("Convert to DOCX")
        self.convert_btn.setObjectName("ConvertButton")
        self.convert_btn.clicked.connect(self.convert_file)

        bottom.addWidget(self.status, 1)
        bottom.addWidget(self.convert_btn)
        layout.addLayout(bottom)

    @property
    def converting(self) -> bool:
        return self._thread is not None

    def set_pdf(self, path: str) -> None:
        self.pdf_edit.setText(path)

    def pick_pdf(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select PDF", "", "PDF Files (*.pdf)")
        if path:
            self.pdf_edit.setText(path)

    def pick_output_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if path:
            self.out_edit.setText(path)

    def convert_file(self) -> None:
        if self.converting:
            return
        pdf = self.pdf_edit.text().strip()
        output_dir = self.out_edit.text().strip() or None

        if not pdf:
            QMessageBox.warning(self, "Missing Info", "Please choose a PDF file.")
            return

        self._set_busy(True)
        self.status.setToolTip("")
        self.status.setText(f"Converting {Path(pdf).name}...")

        thread = ConversionThread(pdf, output_dir, self)
        thread.succeeded.connect(self._keep_outcome)
        thread.failed.connect(self._keep_outcome)
        thread.finished.connect(self._conversion_finished)
        self._thread = thread
        thread.start()

    @Slot(object)
    def _keep_outcome(self, outcome: Result | str) -> None:
        self._outcome = outcome

    @Slot()
    def _conversion_finished(self) -> None:
        thread, self._thread = self._thread, None
        if thread is not None:
            # `finished` is emitted just before the thread's last instruction.
            # wait() returns at once, and makes "done" mean done.
            thread.wait()
            thread.deleteLater()
        outcome, self._outcome = self._outcome, None
        self._set_busy(False)

        if self._close_when_done:
            self.close()
            return
        if isinstance(outcome, Result):
            self._report_success(outcome)
        else:
            self._report_failure(outcome or "The conversion stopped without saying why.")

    def _report_success(self, result: Result) -> None:
        self.status.setText(f"Done: {result.output.name}")
        self.status.setToolTip(str(result.output))
        if result.complete:
            QMessageBox.information(self, "Success", f"Created:\n{result.output}")
            return
        missing = describe_pages(result.skipped)
        verb = "is" if len(result.skipped) == 1 else "are"
        QMessageBox.warning(
            self,
            "Converted, with gaps",
            f"Created:\n{result.output}\n\n"
            f"{missing.capitalize()} could not be converted and {verb} missing from the DOCX.",
        )

    def _report_failure(self, message: str) -> None:
        self.status.setText("Conversion failed.")
        QMessageBox.critical(self, "Error", message)

    def _set_busy(self, busy: bool) -> None:
        for widget in (self.pdf_edit, self.pdf_btn, self.out_edit, self.out_btn, self.convert_btn):
            widget.setEnabled(not busy)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.converting:
            # A conversion cannot be interrupted partway, and quitting while its
            # thread runs aborts the whole process. Let it finish, then close.
            self._close_when_done = True
            self.status.setText("Finishing the conversion, then closing...")
            event.ignore()
            return
        super().closeEvent(event)
