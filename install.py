#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Open Board - Installation Script
Installs Open Board scripts for GIMP 2.10
Supports: macOS, Windows, Linux
"""

import os
import sys
import platform
import shutil
import subprocess
import webbrowser
from pathlib import Path

# ============================================================================
# CONSTANTS
# ============================================================================

VERSION = "1.1"
GIMP_DOWNLOAD_URLS = {
    "Darwin": "https://www.gimp.org/downloads/",
    "Windows": "https://www.gimp.org/downloads/",
    "Linux": "https://www.gimp.org/downloads/"
}

SCRIPT_FILES = [
    "src/createOpenBoard.py",
    "src/importOpenBoard.py",
    "src/addImageNames.py"
]

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def print_header(text):
    """Print formatted header"""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70 + "\n")

def print_success(text):
    """Print success message"""
    print(f"✓ {text}")

def print_error(text):
    """Print error message"""
    print(f"✗ ERROR: {text}")

def print_info(text):
    """Print info message"""
    print(f"ℹ {text}")

def get_gimp_plugin_directory():
    """Get GIMP plugin directory based on OS"""
    system = platform.system()
    home = Path.home()
    
    if system == "Darwin":  # macOS
        paths = [
            home / "Library/Application Support/GIMP/2.10/plug-ins",
            Path("/Applications/GIMP-2.10.app/Contents/Resources/lib/gimp/2.0/plug-ins")
        ]
    elif system == "Windows":
        appdata = os.getenv('APPDATA', home / 'AppData/Roaming')
        paths = [
            Path(appdata) / "GIMP/2.10/plug-ins",
            Path(os.getenv('ProgramFiles', 'C:/Program Files')) / "GIMP 2/lib/gimp/2.0/plug-ins"
        ]
    else:  # Linux
        paths = [
            home / ".config/GIMP/2.10/plug-ins",
            home / ".gimp-2.10/plug-ins",
            Path("/usr/lib/gimp/2.0/plug-ins")
        ]
    
    # Return the first existing path
    for path in paths:
        if path.exists():
            return path
    
    # If none exist, return the first user path and create it
    user_path = paths[0]
    return user_path

def check_gimp_installed():
    """Check if GIMP is installed"""
    system = platform.system()
    
    try:
        if system == "Darwin":  # macOS
            result = subprocess.run(
                ["mdfind", "kMDItemKind == 'Application' && kMDItemDisplayName == 'GIMP*'"],
                capture_output=True, text=True, timeout=5
            )
            return bool(result.stdout.strip())
        
        elif system == "Windows":
            # Check in Program Files
            gimp_paths = [
                Path(os.getenv('ProgramFiles', 'C:/Program Files')) / "GIMP 2",
                Path(os.getenv('ProgramFiles(x86)', 'C:/Program Files (x86)')) / "GIMP 2"
            ]
            return any(path.exists() for path in gimp_paths)
        
        else:  # Linux
            result = subprocess.run(
                ["which", "gimp"],
                capture_output=True, text=True, timeout=5
            )
            return bool(result.stdout.strip())
    
    except Exception as e:
        print_info(f"Could not verify GIMP installation: {e}")
        return False

def download_gimp():
    """Open browser to download GIMP"""
    system = platform.system()
    url = GIMP_DOWNLOAD_URLS.get(system, GIMP_DOWNLOAD_URLS["Linux"])
    
    print_info(f"Opening browser to download GIMP...")
    print_info(f"URL: {url}")
    
    try:
        webbrowser.open(url)
        print_success("Browser opened. Please download and install GIMP 2.10")
        print_info("After installing GIMP, run this script again.")
        return True
    except Exception as e:
        print_error(f"Could not open browser: {e}")
        print_info(f"Please manually download GIMP from: {url}")
        return False

def install_scripts(plugin_dir):
    """Install scripts to GIMP plugin directory"""
    script_dir = Path(__file__).parent
    installed = []
    failed = []
    
    # Create plugin directory if it doesn't exist
    plugin_dir.mkdir(parents=True, exist_ok=True)
    
    for script_file in SCRIPT_FILES:
        source = script_dir / script_file
        
        if not source.exists():
            print_error(f"Script not found: {script_file}")
            failed.append(script_file)
            continue
        
        # Copy to plugin directory
        dest = plugin_dir / source.name
        
        try:
            shutil.copy2(source, dest)
            
            # Make executable on Unix-like systems
            if platform.system() != "Windows":
                os.chmod(dest, 0o755)
            
            print_success(f"Installed: {source.name}")
            installed.append(source.name)
        
        except Exception as e:
            print_error(f"Failed to install {source.name}: {e}")
            failed.append(script_file)
    
    return installed, failed

def show_usage_instructions():
    """Show how to use the installed scripts"""
    print_header("Installation Complete!")
    
    print("The following scripts have been installed:")
    print("  1. Create Board     - Create a new board layout")
    print("  2. Import Images    - Import images into board cells")
    print("  3. Add Image Names  - Add image names as text layers")
    
    print("\n" + "-" * 70)
    print("HOW TO USE:")
    print("-" * 70)
    print("1. Open GIMP")
    print("2. Go to: File > Open Board")
    print("3. Choose the script you want to use")
    print("\nFor creating a new board:")
    print("  File > Open Board > 1.Create Board...")
    print("\nFor importing images into an existing board:")
    print("  File > Open Board > 2.Import Images...")
    print("\nFor adding image names:")
    print("  File > Open Board > 3.Add Image Names...")
    
    print("\n" + "-" * 70)
    print("NOTES:")
    print("-" * 70)
    print("• You may need to restart GIMP to see the new menu items")
    print("• Logs are written to the same folder as your board files")
    print("• To disable logs, edit ENABLE_LOGS = False in each script")
    
    print("\n" + "=" * 70 + "\n")

# ============================================================================
# MAIN INSTALLATION
# ============================================================================

def main():
    """Main installation function"""
    print_header(f"Open Board Installer v{VERSION}")
    
    system = platform.system()
    print_info(f"Detected OS: {system}")
    print_info(f"Python version: {sys.version.split()[0]}")
    
    # Check if GIMP is installed
    print("\n" + "-" * 70)
    print("Checking GIMP installation...")
    print("-" * 70)
    
    if not check_gimp_installed():
        print_error("GIMP 2.10 does not appear to be installed")
        response = input("\nWould you like to download GIMP now? (y/n): ").lower().strip()
        
        if response in ['y', 'yes']:
            download_gimp()
            sys.exit(0)
        else:
            print_info("Please install GIMP 2.10 before running this installer")
            print_info(f"Download from: {GIMP_DOWNLOAD_URLS[system]}")
            sys.exit(1)
    else:
        print_success("GIMP is installed")
    
    # Get plugin directory
    print("\n" + "-" * 70)
    print("Locating GIMP plugin directory...")
    print("-" * 70)
    
    plugin_dir = get_gimp_plugin_directory()
    print_info(f"Plugin directory: {plugin_dir}")
    
    # Confirm installation
    print("\n" + "-" * 70)
    response = input(f"\nInstall scripts to: {plugin_dir}? (y/n): ").lower().strip()
    
    if response not in ['y', 'yes']:
        print_info("Installation cancelled by user")
        sys.exit(0)
    
    # Install scripts
    print("\n" + "-" * 70)
    print("Installing scripts...")
    print("-" * 70 + "\n")
    
    installed, failed = install_scripts(plugin_dir)
    
    # Summary
    print("\n" + "-" * 70)
    print("Installation Summary:")
    print("-" * 70)
    print(f"Successfully installed: {len(installed)}/{len(SCRIPT_FILES)}")
    
    if failed:
        print(f"\nFailed to install:")
        for script in failed:
            print(f"  - {script}")
        print("\nPlease check the error messages above.")
    else:
        show_usage_instructions()
    
    return 0 if not failed else 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nInstallation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

