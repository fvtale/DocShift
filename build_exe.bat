@echo off
setlocal
cd /d %~dp0
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller
pyinstaller --noconfirm --onefile --windowed --name PDFToDOCX --icon app\assets\app.ico --add-data "app\assets\app.ico;app\assets" app\main.py
endlocal
pause
