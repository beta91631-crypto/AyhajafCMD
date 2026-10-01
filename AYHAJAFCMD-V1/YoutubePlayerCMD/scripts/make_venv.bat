@echo off
setlocal
set "PROJECT_ROOT=%~dp0.."
pushd "%PROJECT_ROOT%"

where py >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_CMD=py -3"
) else (
    where python >nul 2>nul
    if errorlevel 1 (
        echo Python 3.10 or newer is required. Install it from https://www.python.org/downloads/.
        popd
        exit /b 1
    )
    set "PYTHON_CMD=python"
)

%PYTHON_CMD% -c "import sys; raise SystemExit(sys.version_info < (3, 10))" >nul 2>nul
if errorlevel 1 (
    echo Python 3.10 or newer is required. Install it from https://www.python.org/downloads/.
    popd
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 (
        echo Could not create the Python virtual environment.
        popd
        exit /b 1
    )
)

".venv\Scripts\python.exe" -c "import yt_dlp; from PIL import Image; from websockets.sync.client import connect; assert hasattr(Image, 'Resampling')" >nul 2>nul
if errorlevel 1 (
    echo Installing YouTubeCMD Python dependencies...
    ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
    if errorlevel 1 (
        echo Dependency installation failed. Check your network connection.
        popd
        exit /b 1
    )
)

popd
exit /b 0