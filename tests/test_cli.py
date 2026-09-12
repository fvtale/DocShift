"""Tests for the command line and the entry point.

CI drives the finished DocShift.exe through this command line, so its contract
-- the exit codes, and exactly one DOCX path per line on stdout -- is pinned
here.
"""

from __future__ import annotations

import sys

import pytest

from docshift import __main__ as entry
from docshift import __version__
from docshift.cli import main


class TestConverting:
    def test_prints_the_path_of_the_docx_and_nothing_else(self, make_pdf, tmp_path, capsys):
        pdf = make_pdf(tmp_path / "report.pdf")
        assert main([str(pdf)]) == 0
        assert capsys.readouterr().out == f"{tmp_path / 'report.docx'}\n"

    def test_output_folder(self, make_pdf, tmp_path):
        pdf = make_pdf(tmp_path / "report.pdf")
        assert main([str(pdf), "--output", str(tmp_path / "out")]) == 0
        assert (tmp_path / "out" / "report.docx").exists()

    def test_keeps_going_past_a_bad_file(self, make_pdf, tmp_path, capsys):
        bad = tmp_path / "bad.pdf"
        bad.write_text("not a pdf")
        good = make_pdf(tmp_path / "good.pdf")
        assert main([str(bad), str(good)]) == 1
        captured = capsys.readouterr()
        assert captured.out == f"{tmp_path / 'good.docx'}\n"
        assert "bad.pdf is not a PDF or a Word document." in captured.err

    def test_never_overwrites_unless_told(self, make_pdf, tmp_path, capsys):
        pdf = make_pdf(tmp_path / "report.pdf")
        (tmp_path / "report.docx").write_text("keep me")

        assert main([str(pdf)]) == 0
        assert capsys.readouterr().out == f"{tmp_path / 'report (1).docx'}\n"
        assert (tmp_path / "report.docx").read_text() == "keep me"

        assert main([str(pdf), "--overwrite"]) == 0
        assert capsys.readouterr().out == f"{tmp_path / 'report.docx'}\n"
        assert (tmp_path / "report.docx").read_bytes()[:2] == b"PK"

    def test_warns_about_missing_pages(self, make_pdf, break_pages, tmp_path, capsys):
        pdf = make_pdf(tmp_path / "report.pdf", ["one", "two", "three"])
        break_pages(2)
        assert main([str(pdf)]) == 0
        err = capsys.readouterr().err
        assert "page 2 of" in err
        assert "is missing from report.docx" in err


class TestUsage:
    def test_version(self, capsys):
        with pytest.raises(SystemExit) as exit_:
            main(["--version"])
        assert exit_.value.code == 0
        assert capsys.readouterr().out.strip() == f"docshift {__version__}"

    def test_options_without_a_file_are_a_usage_error(self):
        with pytest.raises(SystemExit) as exit_:
            main(["--overwrite"])
        assert exit_.value.code == 2


class TestEntryPoint:
    """docshift/__main__.py decides between the window and the command line."""

    def test_arguments_mean_the_command_line(self, make_pdf, tmp_path, capsys):
        pdf = make_pdf(tmp_path / "report.pdf")
        assert entry.main([str(pdf)]) == 0
        assert capsys.readouterr().out == f"{tmp_path / 'report.docx'}\n"

    def test_a_file_from_explorer_opens_the_window(self, monkeypatch):
        # DocShift.exe has no console, so Python gives it no stdout.
        monkeypatch.setattr(sys, "stdout", None)
        assert entry.opened_from_explorer([r"C:\Users\me\report.pdf"])

    def test_several_dropped_files_open_the_window_too(self, monkeypatch):
        # Otherwise they would be converted with nothing on screen to say so.
        monkeypatch.setattr(sys, "stdout", None)
        assert entry.opened_from_explorer([r"C:\a.pdf", r"C:\b.pdf"])

    def test_options_still_mean_the_command_line_without_a_console(self, monkeypatch):
        monkeypatch.setattr(sys, "stdout", None)
        assert not entry.opened_from_explorer(["report.pdf", "--output", "out"])
        assert not entry.opened_from_explorer(["--version"])

    def test_in_a_terminal_a_file_is_the_command_line(self):
        assert not entry.opened_from_explorer(["report.pdf"])
