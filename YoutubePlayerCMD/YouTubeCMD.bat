@echo off
setlocal
pushd "%~dp0"

call scripts\make_venv.bat
if errorlevel 1 goto failed

call scripts\check_ffmpeg.bat
if errorlevel 1 goto failed

".venv\Scripts\python.exe" native\build.py
if errorlevel 1 goto failed

set "PYTHONPATH=%CD%\src"
echo YouTubeCMD
set "STREAM_FILE=%TEMP%\YouTubeCMD-stream-%RANDOM%-%RANDOM%.json"
".venv\Scripts\python.exe" -m youtubecmd.browse %* > "%STREAM_FILE%"
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" goto finished
"bin\renderer.exe" --stream "%STREAM_FILE%" --mode pixel --quality high
set "EXIT_CODE=%ERRORLEVEL%"

:finished
if exist "%STREAM_FILE%" del /q "%STREAM_FILE%"
popd
exit /b %EXIT_CODE%

:failed
popd
pause
exit /b 1