@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title session_to_tdata

echo.
echo ========================================
echo   session to tdata - double-click run
echo ========================================
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo ERROR: Python not found. Install Python 3 and tick "Add to PATH".
  goto :end
)

echo [1/4] Installing packages (skips TgCrypto C++ build)...
python -m pip install --disable-pip-version-check -q -r requirements.txt
python -m pip install --disable-pip-version-check -q opentele==1.15.1 --no-deps
python -m pip install --disable-pip-version-check -q "Telethon>=1.36" pyaes

echo [2/4] Installing crypto shim...
for /f "delims=" %%i in ('python -c "import sysconfig; print(sysconfig.get_path('purelib'))"') do set "SITE=%%i"
if not exist "%SITE%\tgcrypto" mkdir "%SITE%\tgcrypto"
copy /Y "%~dp0vendor\tgcrypto\__init__.py" "%SITE%\tgcrypto\__init__.py" >nul
if errorlevel 1 (
  echo ERROR: Could not install tgcrypto shim. Is vendor\tgcrypto present?
  goto :end
)

echo [3/4] Preparing sessions and tdatas folders...
if not exist "sessions" mkdir sessions
if not exist "tdatas" mkdir tdatas

REM Flatten fix: sessions\NAME.session  ->  sessions\NAME\NAME.session
for %%F in ("sessions\*.session") do (
  if not exist "sessions\%%~nF" mkdir "sessions\%%~nF"
  move /Y "%%~fF" "sessions\%%~nF\%%~nxF" >nul
)

python -c "import tgcrypto; from opentele.tl import TelegramClient" 2>nul
if errorlevel 1 (
  echo ERROR: Imports failed. Check the messages above.
  goto :end
)

echo [4/4] Converting sessions...
echo.
python main.py
echo.

echo ----------------------------------------
echo Done. Output is in the tdatas folder:
dir /b tdatas 2>nul
echo ----------------------------------------
echo.
echo To use in Telegram Desktop:
echo  1. Close Telegram Desktop
echo  2. Backup %%APPDATA%%\Telegram Desktop\tdata
echo  3. Copy contents of tdatas\tdataXXXX into that tdata folder
echo  4. Start Telegram Desktop
echo.

:end
echo.
pause
