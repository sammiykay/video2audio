#!/usr/bin/env python3
"""Universal build script for Vid2Aud - detects platform and runs appropriate build."""

import os
import platform
import subprocess
import sys
from pathlib import Path


def detect_platform():
    """Detect the current platform."""
    system = platform.system()
    if system == "Windows":
        return "windows"
    elif system == "Darwin":
        return "macos"
    elif system == "Linux":
        return "linux"
    else:
        return "unknown"


def check_requirements():
    """Check if required tools are available."""
    try:
        import PyInstaller
        print(f"✓ PyInstaller {PyInstaller.__version__} found")
    except ImportError:
        print("✗ PyInstaller not found. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        print("✓ PyInstaller installed")

    # Check for Python version
    if sys.version_info < (3, 10):
        print(f"✗ Python {sys.version_info.major}.{sys.version_info.minor} detected")
        print("⚠ This application requires Python 3.10 or higher")
        return False
    else:
        print(f"✓ Python {sys.version} is compatible")
    
    return True


def build_windows():
    """Build for Windows."""
    print("🏗️  Building for Windows...")
    
    build_dir = Path(__file__).parent / "build"
    script_path = build_dir / "build_windows.bat"
    
    if script_path.exists():
        os.chdir(Path(__file__).parent)
        subprocess.call([str(script_path)], shell=True)
    else:
        print(f"✗ Build script not found: {script_path}")
        return False
    return True


def build_macos():
    """Build for macOS."""
    print("🏗️  Building for macOS...")
    
    build_dir = Path(__file__).parent / "build"
    script_path = build_dir / "build_macos.sh"
    
    if script_path.exists():
        os.chdir(Path(__file__).parent)
        subprocess.call(["bash", str(script_path)])
    else:
        print(f"✗ Build script not found: {script_path}")
        return False
    return True


def build_linux():
    """Build for Linux."""
    print("🏗️  Building for Linux...")
    
    build_dir = Path(__file__).parent / "build"
    script_path = build_dir / "build_linux.sh"
    
    if script_path.exists():
        os.chdir(Path(__file__).parent)
        subprocess.call(["bash", str(script_path)])
    else:
        print(f"✗ Build script not found: {script_path}")
        return False
    return True


def main():
    """Main build function."""
    print("🎬 Vid2Aud Universal Build Script")
    print("=" * 40)
    
    # Detect platform
    current_platform = detect_platform()
    print(f"🖥️  Detected platform: {current_platform}")
    
    if current_platform == "unknown":
        print("✗ Unsupported platform detected")
        sys.exit(1)
    
    # Check requirements
    if not check_requirements():
        sys.exit(1)
    
    # Build for the current platform
    success = False
    if current_platform == "windows":
        success = build_windows()
    elif current_platform == "macos":
        success = build_macos()
    elif current_platform == "linux":
        success = build_linux()
    
    if success:
        print("\n🎉 Build completed successfully!")
        print(f"📦 Check the 'dist/' and 'installer/' directories for output files")
        
        # Show platform-specific next steps
        if current_platform == "windows":
            print("\n📋 Next steps for Windows:")
            print("• Test the .exe file: dist\\Vid2Aud.exe")
            print("• For distribution, consider creating an installer with Inno Setup")
            
        elif current_platform == "macos":
            print("\n📋 Next steps for macOS:")
            print("• Test the .app bundle: open dist/Vid2Aud.app")
            print("• For distribution, code sign and notarize the app")
            print("• DMG file (if created): installer/Vid2Aud.dmg")
            
        elif current_platform == "linux":
            print("\n📋 Next steps for Linux:")
            print("• Test the executable: ./dist/vid2aud")
            print("• Install package: installer/vid2aud-1.0.0-linux.tar.gz")
            print("• AppImage (if created): installer/Vid2Aud-1.0.0-x86_64.AppImage")
    else:
        print("\n❌ Build failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()