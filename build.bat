@echo off
REM Build script for CSV-XLS Converter
REM Creates standalone exe with PyInstaller and Windows installer with Inno Setup
REM
REM Requirements:
REM   - Python with PyInstaller: pip install pyinstaller
REM   - Inno Setup 6.x: https://jrsoftware.org/isinfo.php
REM
REM Usage:
REM   build.bat         - Build exe only
REM   build.bat full    - Build exe + installer

setlocal enabledelayedexpansion

echo ============================================
echo  CSV-XLS Converter Build Script
echo ============================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found in PATH
    exit /b 1
)

REM Check PyInstaller
python -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo ERROR: PyInstaller not installed. Run: pip install pyinstaller
    exit /b 1
)

REM Get version from _version.py
for /f "tokens=2 delims='" %%a in ('findstr "__version__" _version.py') do set VERSION=%%a
echo Version: %VERSION%
echo.

REM Step 1: Build with PyInstaller
echo [1/2] Building executable with PyInstaller...
echo.

pyinstaller --clean --noconfirm CSV-XLS-Converter.spec

if errorlevel 1 (
    echo.
    echo ERROR: PyInstaller build failed
    exit /b 1
)

echo.
echo PyInstaller build complete: dist\CSV-XLS-Converter.exe
echo.

REM Check if full build requested
if /i "%1"=="full" goto :build_installer
if /i "%1"=="installer" goto :build_installer

echo Build complete! Run 'build.bat full' to also create installer.
goto :eof

:build_installer
REM Step 2: Build installer with Inno Setup
echo [2/2] Building installer with Inno Setup...
echo.

REM Check for Inno Setup compiler
where iscc >nul 2>&1
if errorlevel 1 (
    REM Try common installation paths
    if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
        set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    ) else if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
        set ISCC="C:\Program Files\Inno Setup 6\ISCC.exe"
    ) else (
        echo ERROR: Inno Setup compiler (ISCC) not found
        echo Please install Inno Setup 6 from: https://jrsoftware.org/isinfo.php
        echo Or add ISCC.exe to your PATH
        exit /b 1
    )
) else (
    set ISCC=iscc
)

REM Check if icon exists, create placeholder warning if not
if not exist "assets\icon.ico" (
    echo WARNING: assets\icon.ico not found
    echo Creating assets folder...
    if not exist "assets" mkdir assets
    echo Please add icon.ico to assets folder for proper branding
    echo.
    
    REM Comment out icon line in iss temporarily for build
    echo Building without custom icon...
)

REM Update version in installer script
powershell -Command "(Get-Content installer.iss) -replace '#define MyAppVersion \"[^\"]+\"', '#define MyAppVersion \"%VERSION%\"' | Set-Content installer.iss"

%ISCC% installer.iss

if errorlevel 1 (
    echo.
    echo ERROR: Inno Setup build failed
    exit /b 1
)

echo.
echo ============================================
echo  Build Complete!
echo ============================================
echo.
echo Executable: dist\CSV-XLS-Converter.exe
echo Installer:  dist\CSV-XLS-Converter-Setup-%VERSION%.exe
echo.

:eof
endlocal
