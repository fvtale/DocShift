@echo off
rem Builds dist\DocShift.exe on a Windows machine that has Python 3.11 or newer.
rem
rem You do not need this to get DocShift: CI builds the same .exe on every push
rem to main. See "Get it" in README.md. This is for building one yourself.

setlocal
cd /d "%~dp0.."

python -m pip install --upgrade pip || goto failed
python -m pip install -r requirements.txt pyinstaller || goto failed
python -m PyInstaller --noconfirm --clean packaging\docshift.spec || goto failed

echo.
echo Built dist\DocShift.exe
goto done

:failed
echo.
echo The build failed. The messages above say where.

:done
endlocal
pause
