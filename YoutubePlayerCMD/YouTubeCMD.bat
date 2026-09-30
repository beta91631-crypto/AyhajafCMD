@echo off
setlocal
pushd "%~dp0"

call scripts\make_venv.bat
if errorlevel 1 goto failed

set "PYTHONPATH=%CD%\src"
if /I "%~1"=="--native" goto native

echo YouTubeCMD
".venv\Scripts\python.exe" -m youtubecmd.visual_browser %*
set "EXIT_CODE=%ERRORLEVEL%"
goto finished

:native
shift
call scripts\check_ffmpeg.bat
if errorlevel 1 goto failed

".venv\Scripts\python.exe" native\build.py
if errorlevel 1 goto failed

set "STREAM_FILE=%TEMP%\YouTubeCMD-stream-%RANDOM%-%RANDOM%.json"
".venv\Scripts\python.exe" -m youtubecmd.browse %1 %2 %3 %4 %5 %6 %7 %8 %9 > "%STREAM_FILE%"
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" goto finished
"bin\renderer.exe" --stream "%STREAM_FILE%" --mode pixel --quality high
set "EXIT_CODE=%ERRORLEVEL%"

:finished
if defined STREAM_FILE if exist "%STREAM_FILE%" del /q "%STREAM_FILE%"
popd
exit /b %EXIT_CODE%

:failed
popd
pause
exit /b 1