@echo off
setlocal
pushd "%~dp0"
if not exist "..\bin" mkdir "..\bin"
g++ -static -O2 -Wall -Wextra -std=c++17 src\main.cpp src\console.cpp src\renderer.cpp src\stream.cpp src\media.cpp src\pixel_window.cpp src\player.cpp -o ..\bin\renderer.exe -luser32 -lgdi32
set "BUILD_RESULT=%ERRORLEVEL%"
popd
exit /b %BUILD_RESULT%