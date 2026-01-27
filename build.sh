#!/bin/bash
# Exit immediately if any command fails
set -e

# ---------------------------------------------------------
# Step 1: Version Injection
# ---------------------------------------------------------
# If BUILD_VERSION is set (e.g., from GitHub Actions), replace the version in the source code.
if [ -n "$BUILD_VERSION" ]; then
    echo "Injecting version: $BUILD_VERSION"
    sed -i "s/self.APP_VERSION = \".*\"/self.APP_VERSION = \"$BUILD_VERSION\"/" yocto_tool.py
fi

# ---------------------------------------------------------
# Step 2: System Checks & Dependencies
# ---------------------------------------------------------
# Warn if running as root (sudo), though sometimes necessary for apt-get
if [ "$EUID" -eq 0 ]; then 
    echo "Warning: Running as root."
fi

# Install necessary system packages for Python, GUI (Tkinter), and building tools
echo "Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-tk python3-dev python3-venv binutils git zip

# ---------------------------------------------------------
# Step 3: Virtual Environment Setup
# ---------------------------------------------------------
# Create a temporary virtual environment to isolate build dependencies
echo "Setting up Virtual Environment..."
rm -rf build_env
python3 -m venv build_env

# Activate the virtual environment
source build_env/bin/activate

# Install required Python libraries inside the venv
pip install --upgrade pip
pip install pyinstaller requests

# ---------------------------------------------------------
# Step 4: Clean & Build
# ---------------------------------------------------------
# Remove artifacts from previous builds to ensure a clean state
echo "Cleaning old build files..."
rm -rf build dist __pycache__
rm -f yocto_tool.spec

# Run PyInstaller to create the standalone executable
# --onefile: Bundle everything into a single binary
# --add-data: Include the manager modules inside the binary
# --windowed: Run as a GUI application (no terminal window)
echo "Building YoctoTool..."
pyinstaller --onefile \
    --name="YoctoTool" \
    --add-data="manager_rpi.py:." \
    --add-data="manager_update.py:." \
    --windowed \
    --clean \
    --icon=NONE \
    yocto_tool.py

# ---------------------------------------------------------
# Step 5: Teardown & Verify
# ---------------------------------------------------------
# Exit virtual environment and remove it
deactivate
rm -rf build_env

# Check if the executable was created successfully
if [ -f "dist/YoctoTool" ]; then
    echo "Build success: dist/YoctoTool"
else
    echo "Error: Build failed."
    exit 1
fi