@echo off
where ffmpeg >nul 2>nul
if errorlevel 1 (
    echo FFmpeg was not found in PATH. Install FFmpeg and reopen the terminal.
    exit /b 1
)
where ffplay >nul 2>nul
if errorlevel 1 (
    echo ffplay was not found in PATH. Install an FFmpeg build that includes ffplay.
    exit /b 1
)
exit /b 0