@echo off
REM Build Rust release executables and optional Inno Setup installer.
setlocal enabledelayedexpansion

echo ============================================
echo  CSV-XLS Converter Build Script
echo ============================================
echo.

cargo --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Cargo not found in PATH
    echo Install Rust from: https://rustup.rs
    exit /b 1
)

for /f "tokens=3" %%a in ('findstr "__version__" _version.py') do set VERSION=%%~a
if "%VERSION%"=="" (
    echo ERROR: Unable to read version from _version.py
    exit /b 1
)

echo Version: %VERSION%
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File scripts\sync-version.ps1 -Version "%VERSION%"
if errorlevel 1 (
    echo ERROR: Version sync failed
    exit /b 1
)

echo [1/2] Building Rust release binaries...
cargo build --release -p converter-gui -p converter-cli
if errorlevel 1 (
    echo ERROR: Cargo release build failed
    exit /b 1
)

if not exist "dist" mkdir dist
copy /Y "target\release\csv-xls-converter-gui.exe" "dist\CSV-XLS-Converter.exe" >nul
if errorlevel 1 exit /b 1
copy /Y "target\release\csv-xls-converter.exe" "dist\CSV-XLS-Converter-CLI.exe" >nul
if errorlevel 1 exit /b 1

echo.
echo Rust build complete:
echo   dist\CSV-XLS-Converter.exe
echo   dist\CSV-XLS-Converter-CLI.exe
echo.

if /i "%1"=="full" goto :build_installer
if /i "%1"=="installer" goto :build_installer

echo Build complete. Run build.bat full to also create installer.
goto :eof

:build_installer
echo [2/2] Building installer with Inno Setup...
where iscc >nul 2>&1
if errorlevel 1 (
    if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
        set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    ) else if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
        set ISCC="C:\Program Files\Inno Setup 6\ISCC.exe"
    ) else (
        echo ERROR: Inno Setup compiler ISCC not found
        echo Install Inno Setup 6 from https://jrsoftware.org/isinfo.php
        exit /b 1
    )
) else (
    set ISCC=iscc
)

if not exist "assets\icon.ico" (
    echo WARNING: assets\icon.ico not found; building without custom icon.
    if not exist "assets" mkdir assets
)

%ISCC% installer.iss
if errorlevel 1 (
    echo ERROR: Inno Setup build failed
    exit /b 1
)

echo.
echo ============================================
echo  Build Complete!
echo ============================================
echo.
echo Executable: dist\CSV-XLS-Converter.exe
echo CLI:        dist\CSV-XLS-Converter-CLI.exe
echo Installer:  dist\CSV-XLS-Converter-Setup-%VERSION%.exe
echo.

:eof
endlocal
