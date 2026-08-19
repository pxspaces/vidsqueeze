@echo off
setlocal EnableDelayedExpansion
title HalveIt
cd /d "%~dp0"

echo.
echo   HalveIt
echo   -------
echo.

rem ---------------------------------------------------------------------
rem  Find a Python to run with. We try the ones already on this computer
rem  first, and only download our own copy if there is nothing usable.
rem ---------------------------------------------------------------------

set "PYTHON="

if exist "runtime\python.exe" (
    set "PYTHON=%~dp0runtime\python.exe"
    goto :run
)

py -3 --version >nul 2>&1
if not errorlevel 1 (
    set "PYTHON=py -3"
    goto :run
)

python --version >nul 2>&1
if not errorlevel 1 (
    rem The Microsoft Store stub answers but cannot actually run anything.
    python -c "import sys" >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON=python"
        goto :run
    )
)

rem ---------------------------------------------------------------------
rem  Nothing found. Fetch a private copy into the runtime folder. This
rem  needs no administrator rights and changes nothing outside this folder.
rem ---------------------------------------------------------------------

echo   HalveIt needs Python, which is not installed on this computer.
echo.
echo   It can download a private copy ^(about 11 MB^) into:
echo     %~dp0runtime
echo.
echo   Nothing else on your computer is changed, and deleting the
echo   HalveIt folder removes it completely.
echo.
set /p "AGREE=  Download it now? (Y/N): "
if /i not "!AGREE!"=="Y" (
    echo.
    echo   Cancelled. You can also install Python yourself from python.org
    echo   or with:  winget install Python.Python.3.13
    echo.
    pause
    exit /b 1
)

set "PYVER=3.14.7"
set "PYARCH=amd64"
if /i "%PROCESSOR_ARCHITECTURE%"=="ARM64" set "PYARCH=arm64"
set "PYZIP=python-%PYVER%-embed-%PYARCH%.zip"
set "PYURL=https://www.python.org/ftp/python/%PYVER%/%PYZIP%"

echo.
echo   Downloading Python %PYVER% ...

if not exist ".cache" mkdir ".cache"

curl --version >nul 2>&1
if not errorlevel 1 (
    curl -fL --retry 3 -o ".cache\%PYZIP%" "%PYURL%"
) else (
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
        "$ProgressPreference='SilentlyContinue'; try { Invoke-WebRequest -Uri '%PYURL%' -OutFile '.cache\%PYZIP%' -UseBasicParsing } catch { exit 1 }"
)

if not exist ".cache\%PYZIP%" (
    echo.
    echo   The download failed. Please check your internet connection,
    echo   or install Python yourself from python.org and run this again.
    echo.
    pause
    exit /b 1
)

echo   Unpacking ...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ProgressPreference='SilentlyContinue'; Expand-Archive -LiteralPath '.cache\%PYZIP%' -DestinationPath 'runtime' -Force"

if not exist "runtime\python.exe" (
    echo.
    echo   Unpacking failed. Please install Python yourself from python.org.
    echo.
    pause
    exit /b 1
)

rem This build of Python ignores PYTHONPATH, so the HalveIt folder has to
rem be written into its own path file for our modules to be importable.
for %%F in ("runtime\python*._pth") do (
    findstr /c:"%~dp0" "%%F" >nul 2>&1 || echo %~dp0>>"%%F"
)

del ".cache\%PYZIP%" >nul 2>&1
set "PYTHON=%~dp0runtime\python.exe"
echo   Python is ready.
echo.

rem ---------------------------------------------------------------------
rem  Start HalveIt. It opens in your browser; this window stays open
rem  and does the work.
rem ---------------------------------------------------------------------

:run
%PYTHON% -m halveit %*
set "EXITCODE=%ERRORLEVEL%"

if not "%EXITCODE%"=="0" (
    echo.
    echo   HalveIt stopped unexpectedly ^(code %EXITCODE%^).
    echo   The logs folder may explain why.
    echo.
    pause
)

endlocal
exit /b %EXITCODE%
