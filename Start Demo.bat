@echo off
rem Object Classification Demo - double-click to start (Windows). docs/design.md section 4.
setlocal
rem pushd (not cd): on a network share (UNC path) it maps a temporary drive letter.
pushd "%~dp0"
title Object Classification Demo
set "HERE=%CD%\"
set "LAUNCHED_FROM=%~dp0"

rem Opened straight from the zip, Windows runs it from a temp copy: refuse.
if /i not "%LAUNCHED_FROM:\AppData\Local\Temp\=%"=="%LAUNCHED_FROM%" goto :extract
if /i not "%LAUNCHED_FROM:.zip\=%"=="%LAUNCHED_FROM%" goto :extract

if not exist "%HERE%bin\uv.version" (
  echo This download looks incomplete: bin\uv.version is missing. Download the demo again.
  goto :fail
)

rem Pinned uv: version + SHA-256 per platform live in bin\uv.version.
for /f "usebackq tokens=1,* delims==" %%a in ("%HERE%bin\uv.version") do set "%%a=%%b"
set "UV=%HERE%bin\uv.exe"
set "UV_INSTALL_DIR=%HERE%bin"
set "UV_NO_MODIFY_PATH=1"
set "UV_NO_CONFIG=1"
set "UV_PYTHON_PREFERENCE=only-managed"
set "UV_PYTHON_INSTALL_DIR=%HERE%.uv\python"
set "UV_CACHE_DIR=%HERE%.uv\cache"

if not exist "%UV%" goto :get_uv
"%UV%" --version 2>nul | findstr /b /c:"uv %DEMO_UV_VERSION% " >nul && goto :have_uv
:get_uv
echo Downloading uv %DEMO_UV_VERSION% ...
set "ZIP=%HERE%bin\uv-download.zip"
curl.exe -fL --retry 3 -o "%ZIP%" "https://github.com/astral-sh/uv/releases/download/%DEMO_UV_VERSION%/uv-x86_64-pc-windows-msvc.zip"
if errorlevel 1 (
  echo First-time setup needs internet once.
  goto :fail
)
set "GOT="
for /f "delims=" %%h in ('certutil -hashfile "%ZIP%" SHA256 ^| findstr /v ":"') do set "GOT=%%h"
set "GOT=%GOT: =%"
if /i not "%GOT%"=="%DEMO_UV_SHA256_WINDOWS_X86_64%" (
  del "%ZIP%"
  echo The uv download is damaged. Double-click Start Demo again.
  goto :fail
)
tar -xf "%ZIP%" -C "%HERE%bin" uv.exe
if errorlevel 1 (
  del "%ZIP%"
  echo Could not unpack uv. Double-click Start Demo again.
  goto :fail
)
del "%ZIP%"
:have_uv

rem Torch variant: CUDA 12.x build if an NVIDIA driver is installed, else CPU.
rem A failed GPU check leaves .uv\cuda-unusable so later launches skip the CUDA download.
set "VARIANT=cpu"
where nvidia-smi >nul 2>nul && set "VARIANT=cu12x"
if "%VARIANT%"=="cu12x" if exist "%HERE%.uv\cuda-unusable" (
  set "VARIANT=cpu"
  echo Using CPU. To retry the NVIDIA GPU, delete the file .uv\cuda-unusable in this folder.
)

"%UV%" run --frozen --no-dev --extra %VARIANT% python -m demo.setup --variant %VARIANT%
if errorlevel 4 goto :setup_failed
if errorlevel 3 (
  if not exist "%HERE%.uv" mkdir "%HERE%.uv"
  type nul > "%HERE%.uv\cuda-unusable"
  set "VARIANT=cpu"
  "%UV%" run --frozen --no-dev --extra cpu python -m demo.setup --variant cpu
)
if errorlevel 1 goto :setup_failed

"%UV%" run --frozen --no-dev --extra %VARIANT% python -m demo
if errorlevel 1 goto :fail
popd
exit /b 0

:extract
echo Extract the zip first, then open the extracted folder.
goto :fail

:setup_failed
echo.
echo Setup did not finish. Read the message above, then double-click Start Demo again.

:fail
echo.
pause
popd
exit /b 1
