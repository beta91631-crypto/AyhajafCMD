@echo off
setlocal
pushd "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
    if errorlevel 1 goto failed
)

if not exist ".venv\SocialCMD-deps" (
    ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
    if errorlevel 1 goto failed
    type nul > ".venv\SocialCMD-deps"
)

set "PYTHONPATH=%CD%\src"
".venv\Scripts\python.exe" -m socialcmd.visual_browser %*
set "EXIT_CODE=%ERRORLEVEL%"
popd
exit /b %EXIT_CODE%

:failed
popd
pause
exit /b 1