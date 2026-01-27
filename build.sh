#!/bin/bash
# Exit immediately if any command fails
set -e

echo "=================================="
echo "Yocto Tool Build Script"
echo "=================================="

# ---------------------------------------------------------
# Step 1: Determine Version & Name
# ---------------------------------------------------------
# Nếu có BUILD_VERSION từ CI thì dùng, nếu không thì mặc định là v1.0.0
# Lưu ý: Ta KHÔNG dùng sed để sửa code, mà chỉ đổi tên file exe đầu ra.
VERSION=${BUILD_VERSION:-"v1.0.0"}
EXE_NAME="YoctoTool_${VERSION}"

echo ">> Target Version: $VERSION"
echo ">> Output Filename: $EXE_NAME"

# ---------------------------------------------------------
# Step 2: System Checks & Dependencies
# ---------------------------------------------------------
if [ "$EUID" -eq 0 ]; then 
    echo "Warning: Running as root."
fi

echo "Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-tk python3-dev python3-venv binutils git zip

# ---------------------------------------------------------
# Step 3: Virtual Environment Setup
# ---------------------------------------------------------
echo "Setting up Virtual Environment..."
rm -rf build_env
python3 -m venv build_env

source build_env/bin/activate

pip install --upgrade pip
pip install pyinstaller requests

# ---------------------------------------------------------
# Step 4: Clean & Build
# ---------------------------------------------------------
echo "Cleaning old build files..."
rm -rf build dist __pycache__
rm -f yocto_tool.spec

echo "Building executable..."
# PyInstaller sẽ tạo file có tên nằm trong biến $EXE_NAME (ví dụ YoctoTool_v1.0.0)
pyinstaller --onefile \
    --name="$EXE_NAME" \
    --add-data="manager_rpi.py:." \
    --add-data="manager_update.py:." \
    --windowed \
    --clean \
    --icon=NONE \
    yocto_tool.py

# ---------------------------------------------------------
# Step 5: Teardown & Verify
# ---------------------------------------------------------
deactivate
rm -rf build_env

if [ -f "dist/$EXE_NAME" ]; then
    echo "=================================="
    echo "✓ Build success!"
    echo "File location: dist/$EXE_NAME"
    echo "=================================="
else
    echo "Error: Build failed. File dist/$EXE_NAME not found."
    exit 1
fi