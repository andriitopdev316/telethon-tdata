@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Session-tdata Converter

echo.
echo ========================================
echo   Session ^<-^> tdata Converter
echo ========================================
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo ERROR: Python not found.
  echo Install Python 3.10+ and tick "Add python.exe to PATH".
  goto :end
)

echo [1/3] Installing packages...
python -m pip install --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 (
  echo ERROR: pip install failed.
  goto :end
)
python -m pip install --disable-pip-version-check -q opentele==1.15.1 --no-deps
python -m pip install --disable-pip-version-check -q "Telethon>=1.36" pyaes

echo [2/3] Installing crypto shim...
for /f "delims=" %%i in ('python -c "import sysconfig; print(sysconfig.get_path('purelib'))"') do set "SITE=%%i"
if not exist "%SITE%\tgcrypto" mkdir "%SITE%\tgcrypto"
copy /Y "%~dp0vendor\tgcrypto\__init__.py" "%SITE%\tgcrypto\__init__.py" >nul
if errorlevel 1 (
  echo ERROR: Could not install tgcrypto shim. Is vendor\tgcrypto present?
  goto :end
)

if not exist "sessions" mkdir sessions
if not exist "tdatas" mkdir tdatas

python -c "import tgcrypto; from opentele.td import TDesktop; from PyQt5.QtWidgets import QApplication" 2>nul
if errorlevel 1 (
  echo ERROR: Imports failed. Check the messages above.
  goto :end
)

echo [3/3] Opening app...
echo.
python app.py
if errorlevel 1 (
  echo.
  echo App exited with an error.
  goto :end
)
goto :eof

:end
echo.
pause
