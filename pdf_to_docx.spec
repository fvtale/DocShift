# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

pyside6 = collect_all('PySide6')
pdf2docx = collect_all('pdf2docx')

a = Analysis(
    ['app/main.py'],
    pathex=['.'],
    binaries=pyside6.binaries + pdf2docx.binaries,
    datas=pyside6.datas + pdf2docx.datas + [('app/assets/app.ico', 'app/assets')],
    hiddenimports=pyside6.hiddenimports + pdf2docx.hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='PDFToDOCX',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='app/assets/app.ico',
)
