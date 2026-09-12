# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller recipe for DocShift.exe: one file, no console window.
#
# Run from the repository root:
#
#     pyinstaller --noconfirm --clean packaging/docshift.spec
#
# CI does exactly this on every push -- see the DocShift.exe job in
# .github/workflows/ci.yml -- and that is where the downloadable .exe comes from.
#
# PyInstaller's own hooks decide what to bundle. The first version of this file
# called collect_all() on PySide6, which carries every Qt module -- WebEngine,
# QML, 3D -- into an app that uses three of them.

from pathlib import Path

ROOT = Path(SPECPATH).parent
ICON = ROOT / "docshift" / "gui" / "docshift.ico"

a = Analysis(
    [str(ROOT / "docshift" / "__main__.py")],
    pathex=[str(ROOT)],
    # docshift/gui/app.py loads the icon from beside itself, so it goes in
    # the same place inside the .exe.
    datas=[(str(ICON), "docshift/gui")],
    # The engines. core/convert.py reaches them through importlib by name, so
    # that converting one way never loads the other way's libraries -- and a
    # name assembled at run time is invisible to PyInstaller, which reads the
    # code without running it. Without these two lines the .exe builds happily
    # and then cannot convert anything at all.
    hiddenimports=["docshift.core.pdf_to_docx", "docshift.core.docx_to_pdf"],
    # pdf2docx ships a Tk interface of its own that DocShift never opens.
    # Without this, Tcl/Tk rides along in every download.
    excludes=["tkinter", "pdf2docx.gui"],
)

# Two large libraries DocShift never loads. OpenCV's FFmpeg plugin reads and
# writes video; pdf2docx only runs OpenCV on still images of a page. Qt's
# opengl32sw.dll is a software OpenGL fallback, and a widgets app never draws
# with OpenGL. Together they were 51 MB of a 295 MB bundle -- unpacked again on
# every launch, since a one-file .exe extracts itself each time it starts.
# packaging/smoke_test.py drives the .exe through pdf2docx's OpenCV code to
# prove nothing needed went with them.
UNUSED = ("opencv_videoio_ffmpeg", "opengl32sw")
a.binaries = [entry for entry in a.binaries if not Path(entry[0]).name.startswith(UNUSED)]

pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="DocShift",
    console=False,
    icon=str(ICON),
    # UPX-packed Qt DLLs are a known source of crashes and of antivirus false
    # positives. The download is a little larger, and it opens.
    upx=False,
)
