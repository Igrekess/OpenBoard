# Open Board - Installation Guide

## Overview

Open Board is a collection of GIMP scripts that help you create and manage board layouts for organizing images. This guide will help you install the scripts on **macOS**, **Windows**, or **Linux**.

## Prerequisites

- **GIMP 2.10** (will be offered for download if not installed)
- **Python 3** (usually pre-installed on macOS/Linux, needs installation on Windows)

## Quick Installation

### macOS / Linux

1. Open Terminal
2. Navigate to the OPENBOARD folder:
   ```bash
   cd /path/to/OPENBOARD
   ```
3. Run the installer:
   ```bash
   ./install.sh
   ```

### Windows

1. Open Command Prompt or PowerShell
2. Navigate to the OPENBOARD folder:
   ```cmd
   cd C:\path\to\OPENBOARD
   ```
3. Run the installer:
   ```cmd
   install.bat
   ```

### Alternative: Python Direct

On all platforms, you can also run:
```bash
python3 install.py
```
or
```cmd
python install.py
```

## What the Installer Does

1. ✓ Detects your operating system
2. ✓ Checks if GIMP 2.10 is installed
3. ✓ Offers to download GIMP if not found
4. ✓ Locates your GIMP plugin directory
5. ✓ Copies the three scripts to the correct location
6. ✓ Sets proper file permissions (macOS/Linux)

## Installation Locations

The scripts will be installed to:

- **macOS**: `~/Library/Application Support/GIMP/2.10/plug-ins/`
- **Windows**: `%APPDATA%\GIMP\2.10\plug-ins\`
- **Linux**: `~/.config/GIMP/2.10/plug-ins/`

## After Installation

1. **Restart GIMP** (if it was already running)
2. The scripts will appear in GIMP under: **File > Open Board**
3. You'll see three menu items:
   - `1.Create Board...` - Create a new board layout
   - `2.Import Images...` - Import images into board cells
   - `3.Add Image Names...` - Add image names as text layers

## Usage

### Creating a Board

1. Go to: **File > Open Board > 1.Create Board...**
2. Configure:
   - Board name and destination folder
   - Canvas size and resolution
   - Number of rows and columns
   - Cell type (single or spread)
   - Colors, margins, spacing
3. Click **OK** to generate the board

### Importing Images

1. Open your board XCF file in GIMP
2. Go to: **File > Open Board > 2.Import Images...**
3. Configure:
   - Import mode (folder, single file, or pattern)
   - Source folder/file
   - Cell type and resize mode
   - Optional: auto-extend board
4. Click **OK** to import

### Adding Image Names

1. Open your board XCF file with images in GIMP
2. Go to: **File > Open Board > 3.Add Image Names...**
3. Configure:
   - Font and size (default: Sans, 25px)
   - Color (default: white)
   - Distance from cell (default: 20px)
4. Click **OK** to add names

## Troubleshooting

### GIMP Not Found

If the installer can't find GIMP:
- Make sure GIMP 2.10 is installed
- On Windows, try reinstalling GIMP with default paths
- On macOS, check `/Applications/GIMP-2.10.app`
- On Linux, install via package manager: `sudo apt install gimp` (Ubuntu/Debian)

### Python Not Found (Windows)

If Python is not found:
1. Download from: https://www.python.org/downloads/
2. During installation, **check "Add Python to PATH"**
3. Restart Command Prompt and try again

### Scripts Don't Appear in GIMP

1. Restart GIMP completely
2. Check that files are in the correct plugin directory
3. On macOS/Linux, verify files are executable: `chmod +x ~/.config/GIMP/2.10/plug-ins/*.py`

### Permission Denied (macOS/Linux)

If you get permission errors:
```bash
chmod +x install.sh
./install.sh
```

Or run with sudo (not recommended unless necessary):
```bash
sudo ./install.sh
```

## Manual Installation

If the automated installer doesn't work, you can install manually:

1. Locate your GIMP plugin directory (see "Installation Locations" above)
2. Copy these three files from `src/` to the plugin directory:
   - `createOpenBoard.py`
   - `importOpenBoard.py`
   - `addImageNames.py`
3. On macOS/Linux, make them executable:
   ```bash
   chmod +x ~/.config/GIMP/2.10/plug-ins/*.py
   ```
4. Restart GIMP

## Uninstallation

To remove the scripts:

1. Navigate to your GIMP plugin directory
2. Delete the three script files:
   - `createOpenBoard.py`
   - `importOpenBoard.py`
   - `addImageNames.py`
3. Restart GIMP

## Configuration

### Disabling Logs

To disable log file creation, edit each script and change:
```python
ENABLE_LOGS = True
```
to:
```python
ENABLE_LOGS = False
```

The scripts are located in your GIMP plugin directory.

## Support

For issues or questions:
- Check the log files created in your board folders
- File format: `[BoardName]_import.log`, `[BoardName]_add_names.log`
- Review error messages in the GIMP console

## Version

Open Board v1.1
Compatible with GIMP 2.10

---

**Author**: Yan Senez  
**License**: See LICENSE file

