import subprocess
import threading
import os
import shlex
import re
from tkinter import messagebox

class BuildManager:
    def __init__(self, app):
        self.app = app

    def start_build_thread(self):
        if not self.app.poky_path.get(): return
        self.app.set_busy_state(True)
        threading.Thread(target=self.run_build).start()

    def start_clean_thread(self):
        if not self.app.poky_path.get(): return
        if messagebox.askyesno("Confirm", "Clean build?"):
            self.app.set_busy_state(True)
            threading.Thread(target=self.run_clean).start()

    def start_specific_build(self, target):
        if not self.app.poky_path.get(): return
        self.app.set_busy_state(True)
        threading.Thread(target=self.run_build, args=(target,)).start()

    def check_and_download_layers(self):
        poky = self.app.poky_path.get()
        if not poky or not os.path.isdir(poky): return

        try:
            branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=poky, text=True).strip()
            if branch == "HEAD": branch = "scarthgap"
        except: branch = "scarthgap"
        self.app.log(f"Detected Poky branch: {branch}")

        required_layers = []
        if self.app.active_manager:
            required_layers.extend(self.app.active_manager.get_required_layers())
            
        # OTA Tab layers are dynamic (Mender OR RAUC)
        if hasattr(self.app.tab_ota, 'get_required_layers'):
             required_layers.extend(self.app.tab_ota.get_required_layers())

        for name, url_info in required_layers:
            path = os.path.join(poky, name)
            if not os.path.exists(path):
                self.app.log(f"Missing layer {name}. Cloning...")
                
                clone_args = ["git", "clone", "--progress"]
                target_branch = branch
                
                parts = url_info.split()
                actual_url = parts[0]
                
                if "-b" in parts:
                    try:
                        idx = parts.index("-b")
                        if idx + 1 < len(parts):
                            target_branch = parts[idx+1]
                    except: pass
                
                clone_args.extend(["-b", target_branch, actual_url, path])
                
                self.app.log(f"Running: {' '.join(clone_args)}")
                success = self.app.mgr_setup.exec_stream_cmd(clone_args)
                
                if not success:
                    self.app.log(f"Failed to clone {name} ({target_branch}). Retrying without branch...")
                    self.app.mgr_setup.exec_stream_cmd(["git", "clone", "--progress", actual_url, path])

        self.app.log("Layer check complete.")

    def run_build(self, target=None):
        try:
            # Call Setup Manager to sync configs
            self.app.mgr_setup.regenerate_bblayers()
            self.check_and_download_layers()
            
            # Call OTA Tab to fix issues (if applicable for Mender)
            needs_clean = False
            if hasattr(self.app.tab_ota, 'apply_mender_fixes'):
                needs_clean = self.app.tab_ota.apply_mender_fixes()

            build_target = target if target else self.app.tab_general.image_var.get()
            self.app.log(f"Building {build_target}...")
            
            cmd = f"bitbake {build_target}"
            
            if needs_clean:
                self.app.log("Applying Cleanall on U-Boot to ensure fix works...")
                cmd = f"bitbake -c cleanall u-boot && {cmd}"
                
            self.exec_user_cmd(cmd)

            # Hint for RAUC Bundle: If user just built the Image, remind them to build the Bundle
            if hasattr(self.app.tab_ota, 'ota_mode') and \
               self.app.tab_ota.ota_mode.get() == "RAUC" and target is None:
                self.app.log("-" * 40)
                self.app.log("[INFO] RAUC Mode Active:")
                self.app.log("1. Flash the generated .wic file to SD Card.")
                self.app.log("2. Go to OTA Tab and click 'BUILD RAUC BUNDLE' to create update file.")
                self.app.log("-" * 40)
        finally:
            self.app.root.after(0, self.app.set_busy_state, False)

    def run_clean(self):
        try:
            self.app.log("Cleaning...")
            self.exec_user_cmd(f"bitbake -c cleanall {self.app.tab_general.image_var.get()}")
        finally:
            self.app.root.after(0, self.app.set_busy_state, False)

    def exec_user_cmd(self, cmd):
        safe_poky = shlex.quote(self.app.poky_path.get())
        safe_build = shlex.quote(self.app.build_dir_name.get())
        full_cmd = f"sudo -u {self.app.sudo_user} bash -c 'cd {safe_poky} && source oe-init-build-env {safe_build} && {cmd}'"
        
        self.app.root.after(0, lambda: self.app.pb_canvas.itemconfig(self.app.pb_rect, fill="#4CAF50"))
        
        proc = subprocess.Popen(full_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
        self.app.root.after(0, self.app.build_progress.set, 0)
        self.app.root.after(0, self.app.build_progress_text.set, "0%")
        
        while True:
            line = proc.stdout.readline()
            if not line and proc.poll() is not None: break
            if line:
                self.app.log(line.strip())
                m = re.search(r'Running task (\d+) of (\d+)', line)
                if m:
                    current = int(m.group(1))
                    total = int(m.group(2))
                    if total > 0:
                        percent = (current / total) * 100
                        self.app.root.after(0, self.app.build_progress.set, percent)
                        self.app.root.after(0, self.app.build_progress_text.set, f"{int(percent)}%")
                
        if proc.returncode == 0: 
            self.app.root.after(0, self.app.build_progress.set, 100)
            self.app.root.after(0, self.app.build_progress_text.set, "100%") 
            self.app.root.after(0, messagebox.showinfo, "Success", "Done!")
        else: 
            self.app.root.after(0, lambda: self.app.pb_canvas.itemconfig(self.app.pb_rect, fill="#FF0000"))
            self.app.root.after(0, messagebox.showerror, "Error", "Failed!")