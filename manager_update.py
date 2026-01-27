import os
import sys
import tempfile
import shutil
import zipfile
import requests
import subprocess
import datetime
import threading
import stat
import tkinter as tk
from tkinter import ttk, messagebox

GITHUB_REPO = "thebarusa/YoctoTool" 
GITHUB_API = f"https://api.github.com/repos/{GITHUB_REPO}"
GITHUB_RELEASE_URL = f"{GITHUB_API}/releases/latest"

GITHUB_TOKEN = "" 

GITHUB_HEADERS = {
    "Accept": "application/vnd.github+json",
    **({"Authorization": f"Bearer {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}),
}

def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

# =========================================================================
# LOGIC KIỂM TRA PHIÊN BẢN
# =========================================================================

def should_update(current_version: str, remote_version: str) -> bool:
    """So sánh version dạng v1.0.0"""
    def parse(v):
        return tuple(map(int, (v.lstrip("v").split("."))))
    
    try:
        return parse(remote_version) > parse(current_version)
    except:
        # Nếu format version lạ, luôn báo update nếu string khác nhau
        return current_version != remote_version

def check_for_update(parent_window, current_version):
    """Hàm được gọi từ YoctoTool"""
    threading.Thread(target=_check_update_thread, args=(parent_window, current_version), daemon=True).start()

def _check_update_thread(root, current_version):
    try:
        resp = requests.get(GITHUB_RELEASE_URL, headers=GITHUB_HEADERS, timeout=5)
        if resp.status_code != 200:
            root.after(0, lambda: messagebox.showerror("Update Error", f"Cannot check update.\nGitHub code: {resp.status_code}"))
            return

        release = resp.json()
        latest_version = release.get("tag_name", "v0.0.0")
        changelog = release.get("body", "No details.")
        assets = release.get("assets", [])

        if not should_update(current_version, latest_version):
            root.after(0, lambda: messagebox.showinfo("Update", f"YoctoTool is up to date.\nCurrent: {current_version}"))
            return

        download_url = assets[0].get("browser_download_url", "") if assets else None
        
        def ask_user():
            msg = (f"🔔 NEW VERSION AVAILABLE: {latest_version}\n\n"
                   f"Current: {current_version}\n\n"
                   f"Changelog:\n{changelog}\n\n"
                   "Do you want to update now?")
            
            if messagebox.askyesno("Update YoctoTool", msg):
                if download_url:
                    download_popup(root, download_url, latest_version)
                else:
                    messagebox.warning("Error", "No release asset found.")
        
        root.after(0, ask_user)

    except Exception as e:
        root.after(0, lambda: messagebox.showerror("Connection Error", f"Check failed:\n{e}"))

# =========================================================================
# GIAO DIỆN & TẢI XUỐNG
# =========================================================================

def download_popup(parent, download_url, version):
    top = tk.Toplevel(parent)
    top.title(f"Downloading {version}")
    top.geometry("400x150")
    
    # Center popup
    x = parent.winfo_x() + (parent.winfo_width() // 2) - 200
    y = parent.winfo_y() + (parent.winfo_height() // 2) - 75
    top.geometry(f"+{x}+{y}")

    lbl = tk.Label(top, text="Starting download...", anchor="w")
    lbl.pack(fill="x", padx=20, pady=20)
    
    pb = ttk.Progressbar(top, length=350, mode="determinate")
    pb.pack(padx=20)
    
    threading.Thread(target=_download_worker, args=(download_url, version, top, pb, lbl), daemon=True).start()

def _download_worker(url, version, top, pb, lbl):
    try:
        # Nếu repo private, cần đổi URL sang API asset (code cũ đã có logic này, giữ đơn giản cho public)
        tmp_zip = os.path.join(tempfile.gettempdir(), f"yocto_update_{version}.zip")
        extract_dir = os.path.join(tempfile.gettempdir(), f"yocto_extract_{version}")

        # 1. Download
        lbl.config(text="Downloading...")
        with requests.get(url, headers=GITHUB_HEADERS, stream=True, timeout=60) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            downloaded = 0
            with open(tmp_zip, "wb") as f:
                for chunk in r.iter_content(1024*32):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = int(downloaded * 100 / total)
                        top.after(0, lambda p=pct: pb.config(value=p))
        
        # 2. Extract
        lbl.config(text="Extracting...")
        if os.path.exists(extract_dir): shutil.rmtree(extract_dir)
        
        with zipfile.ZipFile(tmp_zip, "r") as zf:
            zf.extractall(extract_dir)

        # Xử lý nested folder (nếu zip chứa thư mục con)
        items = os.listdir(extract_dir)
        if len(items) == 1 and os.path.isdir(os.path.join(extract_dir, items[0])):
            extract_dir = os.path.join(extract_dir, items[0])

        # 3. Install
        lbl.config(text="Installing...")
        top.after(1000, lambda: run_linux_updater(extract_dir))

    except Exception as e:
        top.after(0, lambda: messagebox.showerror("Error", str(e)))
        top.after(0, top.destroy)

# =========================================================================
# SCRIPT CẬP NHẬT (LINUX SUDO)
# =========================================================================

def run_linux_updater(new_dir):
    """Tạo bash script để copy đè file và restart"""
    
    # Xác định file exe đang chạy
    if getattr(sys, 'frozen', False):
        current_exe = sys.executable
        app_dir = os.path.dirname(current_exe)
        exe_name = os.path.basename(current_exe)
    else:
        # Chạy source code (chỉ để test)
        current_exe = os.path.abspath(sys.argv[0])
        app_dir = os.path.dirname(current_exe)
        exe_name = "yocto_tool.py"

    script_path = os.path.join(tempfile.gettempdir(), "yocto_updater.sh")
    
    # Lệnh restart (giữ sudo)
    if getattr(sys, 'frozen', False):
        restart_cmd = f'sudo "{os.path.join(app_dir, exe_name)}" &'
    else:
        restart_cmd = f'sudo python3 "{os.path.join(app_dir, exe_name)}" &'

    bash_content = f"""#!/bin/bash
sleep 2
echo "Updating YoctoTool..."

# 1. Copy file mới đè vào thư mục app
cp -rf "{new_dir}/"* "{app_dir}/"

# 2. Đảm bảo quyền thực thi
chmod +x "{os.path.join(app_dir, exe_name)}"

# 3. Dọn dẹp
rm -rf "{new_dir}"

# 4. Khởi động lại app
echo "Restarting..."
{restart_cmd}

# 5. Xóa script này
rm -- "$0"
"""
    
    with open(script_path, "w") as f:
        f.write(bash_content)
    
    os.chmod(script_path, 0o755)
    
    # Chạy script độc lập
    subprocess.Popen(["/bin/bash", script_path], start_new_session=True)
    sys.exit(0)