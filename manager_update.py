import os
import sys
import tempfile
import shutil
import zipfile
import requests
import subprocess
import threading
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

def should_update(current_version: str, remote_version: str) -> bool:
    def parse(v):
        clean_v = v.lstrip("v").strip()
        try:
            return tuple(map(int, clean_v.split(".")))
        except ValueError:
            return (0, 0, 0)
    
    curr = parse(current_version)
    rem = parse(remote_version)
    return rem > curr

def check_for_update(parent_window, current_version):
    threading.Thread(target=_check_update_thread, args=(parent_window, current_version), daemon=True).start()

def _check_update_thread(root, current_version):
    try:
        resp = requests.get(GITHUB_RELEASE_URL, headers=GITHUB_HEADERS, timeout=5)
        
        if resp.status_code == 404:
             root.after(0, lambda: messagebox.showinfo("Update Check", "No releases found."))
             return
        if resp.status_code != 200:
            root.after(0, lambda: messagebox.showerror("Update Error", f"Cannot check update.\nCode: {resp.status_code}"))
            return

        release = resp.json()
        latest_version = release.get("tag_name", "v0.0.0")
        changelog = release.get("body", "No details available.")
        assets = release.get("assets", [])

        if not should_update(current_version, latest_version):
            msg = f"App is up to date.\nCurrent: {current_version}\nLatest: {latest_version}"
            root.after(0, lambda: messagebox.showinfo("Update Check", msg))
            return

        download_url = assets[0].get("browser_download_url", "") if assets else None
        
        def ask_user():
            msg = (f"New version available: {latest_version}\n\n"
                   f"Current: {current_version}\n\n"
                   f"Changelog:\n{changelog}\n\n"
                   "Update now?")
            
            if messagebox.askyesno("Update YoctoTool", msg):
                if download_url:
                    download_popup(root, download_url, latest_version)
                else:
                    messagebox.warning("Error", "No asset found.")
        
        root.after(0, ask_user)

    except Exception as e:
        root.after(0, lambda: messagebox.showerror("Connection Error", str(e)))

def download_popup(parent, download_url, version):
    top = tk.Toplevel(parent)
    top.title(f"Downloading {version}")
    top.geometry("400x150")
    
    try:
        x = parent.winfo_x() + (parent.winfo_width() // 2) - 200
        y = parent.winfo_y() + (parent.winfo_height() // 2) - 75
        top.geometry(f"+{x}+{y}")
    except: pass

    lbl = tk.Label(top, text="Starting download...", anchor="w")
    lbl.pack(fill="x", padx=20, pady=20)
    
    pb = ttk.Progressbar(top, length=350, mode="determinate")
    pb.pack(padx=20)
    
    threading.Thread(target=_download_worker, args=(download_url, version, top, pb, lbl), daemon=True).start()

def _download_worker(url, version, top, pb, lbl):
    try:
        tmp_dir = tempfile.gettempdir()
        tmp_zip = os.path.join(tmp_dir, f"yocto_update_{version}.zip")
        extract_dir = os.path.join(tmp_dir, f"yocto_extract_{version}")

        lbl.config(text="Downloading...")
        with requests.get(url, headers=GITHUB_HEADERS, stream=True, timeout=60) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            downloaded = 0
            with open(tmp_zip, "wb") as f:
                for chunk in r.iter_content(1024*32):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total:
                            pct = int(downloaded * 100 / total)
                            top.after(0, lambda p=pct: pb.config(value=p))
        
        lbl.config(text="Extracting...")
        if os.path.exists(extract_dir): shutil.rmtree(extract_dir)
        
        if zipfile.is_zipfile(tmp_zip):
            with zipfile.ZipFile(tmp_zip, "r") as zf:
                zf.extractall(extract_dir)
            
            items = os.listdir(extract_dir)
            if len(items) == 1:
                potential_dir = os.path.join(extract_dir, items[0])
                if os.path.isdir(potential_dir):
                    extract_dir = potential_dir
        else:
            os.makedirs(extract_dir, exist_ok=True)
            shutil.copy(tmp_zip, os.path.join(extract_dir, "YoctoTool"))

        lbl.config(text="Installing...")
        top.after(1000, lambda: run_linux_updater(extract_dir))

    except Exception as e:
        top.after(0, lambda: messagebox.showerror("Update Error", str(e)))
        top.after(0, top.destroy)

def run_linux_updater(new_dir):
    if getattr(sys, 'frozen', False):
        current_exe = sys.executable
        app_dir = os.path.dirname(current_exe)
        exe_name = os.path.basename(current_exe)
        restart_cmd = f'"{os.path.join(app_dir, exe_name)}" &'
    else:
        current_exe = os.path.abspath(sys.argv[0])
        app_dir = os.path.dirname(current_exe)
        exe_name = "yocto_tool.py"
        restart_cmd = f'python3 "{os.path.join(app_dir, exe_name)}" &'

    script_path = os.path.join(tempfile.gettempdir(), "yocto_updater.sh")
    
    bash_content = f"""#!/bin/bash
sleep 2
SOURCE_DIR="{new_dir}"
DEST_DIR="{app_dir}"
EXE_NAME="{exe_name}"
cp -rf "$SOURCE_DIR/"* "$DEST_DIR/"
chmod +x "$DEST_DIR/$EXE_NAME"
rm -rf "$SOURCE_DIR"
cd "$DEST_DIR"
{restart_cmd}
rm -- "$0"
"""
    
    with open(script_path, "w") as f:
        f.write(bash_content)
    
    os.chmod(script_path, 0o755)
    subprocess.Popen(["/bin/bash", script_path], start_new_session=True)
    sys.exit(0)