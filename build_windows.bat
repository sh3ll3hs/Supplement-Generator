@echo off
REM Builds "dist\Supplement Maker.exe". Needs Python 3.10+ from python.org (check "Add to PATH").
cd /d "%~dp0"
py -3 -m venv .venv || python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller --noconfirm SupplementMaker.spec
echo.
echo Done: dist\Supplement Maker.exe
pause
