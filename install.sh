#!/bin/bash
# Open Board - Installation Script for macOS/Linux
# This script will install Open Board scripts for GIMP 2.10

set -e  # Exit on error

echo "========================================================================"
echo "  Open Board - GIMP Scripts Installer"
echo "  For macOS and Linux"
echo "========================================================================"
echo ""

# Check if Python 3 is available
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "✗ ERROR: Python is not installed"
    echo "  Please install Python 3 first"
    exit 1
fi

echo "Using: $PYTHON_CMD"
echo ""

# Run the Python installer
$PYTHON_CMD install.py "$@"

exit $?

