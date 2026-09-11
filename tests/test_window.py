"""Tests for the window, driven headless on Qt's offscreen platform.

Message boxes are swapped for a recorder: a real QMessageBox is modal, and
would wait forever for a click no test can make.
"""

from __future__ import annotations

import time

import pytest

from docshift.gui import window as window_module
from docshift.gui.window import MainWindow


def settle(qapp, window, timeout=120.0):
    """Run Qt's event loop until the window has no conversion in flight."""
    deadline = time.monotonic() + timeout
    while window.converting:
        assert time.monotonic() < deadline, "the conversion never finished"
        qapp.processEvents()
        time.sleep(0.01)
    qapp.processEvents()


@pytest.fixture
def dialogs(monkeypatch):
    shown = []

    class Recorder:
        @staticmethod
        def information(parent, title, text):
            shown.append(("information", title, text))

        @staticmethod
        def warning(parent, title, text):
            shown.append(("warning", title, text))

        @staticmethod
        def critical(parent, title, text):
            shown.append(("critical", title, text))

    monkeypatch.setattr(window_module, "QMessageBox", Recorder)
    return shown


@pytest.fixture
def window(qapp, dialogs):
    win = MainWindow()
    win.show()
    yield win
    settle(qapp, win)
    win.close()
    win.deleteLater()
    qapp.processEvents()


def controls_enabled(win) -> bool:
    return all(
        widget.isEnabled()
        for widget in (win.pdf_edit, win.pdf_btn, win.out_edit, win.out_btn, win.convert_btn)
    )


class TestStart:
    def test_ready(self, window):
        assert window.windowTitle() == "DocShift"
        assert window.status.text() == "Ready."
        assert controls_enabled(window)

    def test_cannot_be_squeezed_until_text_is_cut_off(self, qapp, window):
        window.resize(640, 200)
        qapp.processEvents()
        for box in (window.pdf_edit, window.out_edit, window.convert_btn):
            assert box.height() >= box.sizeHint().height(), box

    def test_a_pdf_can_arrive_filled_in(self, window):
        window.set_pdf(r"C:\Users\me\report.pdf")
        assert window.pdf_edit.text() == r"C:\Users\me\report.pdf"


class TestConverting:
    def test_asks_for_a_pdf_first(self, window, dialogs):
        window.convert_btn.click()
        assert dialogs == [("warning", "Missing Info", "Please choose a PDF file.")]
        assert not window.converting

    def test_converts_beside_the_pdf(self, qapp, window, dialogs, make_pdf, tmp_path):
        pdf = make_pdf(tmp_path / "report.pdf")
        window.set_pdf(str(pdf))
        window.convert_btn.click()

        assert window.converting
        assert not controls_enabled(window)
        assert window.status.text() == "Converting report.pdf..."

        settle(qapp, window)
        docx = tmp_path / "report.docx"
        assert docx.exists()
        assert dialogs == [("information", "Success", f"Created:\n{docx}")]
        assert window.status.text() == "Done: report.docx"
        assert controls_enabled(window)

    def test_uses_the_chosen_folder(self, qapp, window, make_pdf, tmp_path):
        pdf = make_pdf(tmp_path / "report.pdf")
        window.set_pdf(str(pdf))
        window.out_edit.setText(str(tmp_path / "out"))
        window.convert_btn.click()
        settle(qapp, window)
        assert (tmp_path / "out" / "report.docx").exists()

    def test_a_bad_file_is_reported(self, qapp, window, dialogs, tmp_path):
        fake = tmp_path / "fake.pdf"
        fake.write_text("not a pdf")
        window.set_pdf(str(fake))
        window.convert_btn.click()
        settle(qapp, window)
        assert dialogs == [("critical", "Error", "fake.pdf is not a PDF.")]
        assert window.status.text() == "Conversion failed."
        assert controls_enabled(window)

    def test_missing_pages_are_reported(self, qapp, window, dialogs, make_pdf, break_pages, tmp_path):
        pdf = make_pdf(tmp_path / "report.pdf", ["one", "two", "three"])
        break_pages(2)
        window.set_pdf(str(pdf))
        window.convert_btn.click()
        settle(qapp, window)
        [(kind, title, text)] = dialogs
        assert (kind, title) == ("warning", "Converted, with gaps")
        assert "Page 2 could not be converted and is missing from the DOCX." in text


class TestClosing:
    def test_waits_for_the_conversion_then_closes(self, qapp, window, dialogs, make_pdf, tmp_path):
        pdf = make_pdf(tmp_path / "report.pdf")
        window.set_pdf(str(pdf))
        window.convert_btn.click()

        assert not window.close(), "closed under a running conversion"
        assert window.isVisible()
        assert window.status.text() == "Finishing the conversion, then closing..."

        settle(qapp, window)
        assert not window.isVisible()
        assert (tmp_path / "report.docx").exists()
        # They were leaving. No "Success" box stands in the way.
        assert dialogs == []
