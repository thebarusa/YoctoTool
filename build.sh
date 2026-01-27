#!/bin/bash
# Build script for Yocto Tool
# Fixed for Ubuntu 24.04+ (PEP 668) using Virtual Environment

set -e  # Exit on error

echo "=================================="
echo "Yocto Tool Build Script"
echo "=================================="

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
    echo "Warning: Running as root. Ensure you are in the correct directory."
fi

echo ""
echo "Step 1: Installing system dependencies..."
echo "=========================================="

# Install system packages
sudo apt-get update
sudo apt-get install -y \
    python3 \
    python3-pip \
    python3-tk \
    python3-dev \
    python3-venv \
    binutils \
    git

echo "✓ System dependencies installed"

echo ""
echo "Step 2: Setting up Virtual Environment..."
echo "=========================================="

# Create a virtual environment named 'build_env'
rm -rf build_env
python3 -m venv build_env

# Activate the virtual environment
source build_env/bin/activate

# Upgrade pip inside the venv
pip install --upgrade pip

# Install PyInstaller and Requests inside the venv
pip install pyinstaller requests

echo "✓ Virtual Environment ready"

echo ""
echo "Step 3: Building standalone executable..."
echo "=========================================="

# Clean previous builds
rm -rf build dist __pycache__
rm -f yocto_tool.spec

# Build with PyInstaller
# --add-data: Đóng gói thêm file source manager_rpi và manager_update nếu cần import động
pyinstaller --onefile \
    --name="YoctoTool" \
    --add-data="manager_rpi.py:." \
    --add-data="manager_update.py:." \
    --windowed \
    --clean \
    --icon=NONE \
    yocto_tool.py

# Deactivate and remove the virtual environment
deactivate
rm -rf build_env

echo "✓ Build completed!"

echo ""
echo "=================================="
echo "Build Summary"
echo "=================================="
if [ -f "dist/YoctoTool" ]; then
    echo "Executable location: dist/YoctoTool"
    echo "Size: $(du -h dist/YoctoTool | cut -f1)"
    echo ""
    echo "To run the standalone executable:"
    echo "  sudo ./dist/YoctoTool"
    echo ""
    echo "To install system-wide (optional):"
    echo "  sudo cp dist/YoctoTool /usr/local/bin/"
    echo "  sudo YoctoTool"
else
    echo "Error: Build failed. Executable not found."
    exit 1
fi
echo "=================================="