@echo off
REM Open Board - Installation Script for Windows
REM This script will install Open Board scripts for GIMP 2.10

echo ========================================================================
echo   Open Board - GIMP Scripts Installer
echo   For Windows
echo ========================================================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo X ERROR: Python is not installed
    echo   Please install Python 3 from https://www.python.org/downloads/
    echo   Make sure to check "Add Python to PATH" during installation
    pause
    exit /b 1
)

echo Using Python:
python --version
echo.

REM Run the Python installer
python install.py %*

if %errorlevel% neq 0 (
    echo.
    echo Installation failed. Please check the errors above.
    pause
    exit /b %errorlevel%
)

pause
exit /b 0

