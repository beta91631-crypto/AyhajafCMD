@echo off
setlocal
pushd "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
    if errorlevel 1 goto failed
)

".venv\Scripts\python.exe" -c "import PIL, playwright" >nul 2>&1
if errorlevel 1 (
    ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -e .
    if errorlevel 1 goto failed
)

".venv\Scripts\python.exe" -c "from playwright.sync_api import sync_playwright; import os, sys; p=sync_playwright().start(); ok=os.path.isfile(p.chromium.executable_path); p.stop(); sys.exit(0 if ok else 1)" >nul 2>&1
if errorlevel 1 (
    ".venv\Scripts\python.exe" -m playwright install chromium
    if errorlevel 1 goto failed
)

set "PYTHONPATH=%CD%\src"
".venv\Scripts\python.exe" -m socialcmd_v2 %*
set "EXIT_CODE=%ERRORLEVEL%"
popd
exit /b %EXIT_CODE%

:failed
echo V2 setup failed. Check that Python is installed and internet access is available.
popd
pause
exit /b 1
