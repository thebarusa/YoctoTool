import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import subprocess
import threading
import json
import re
import shlex

class SetupManager:
    def __init__(self, app):
        self.app = app # Reference to main YoctoolApp

    def browse_folder(self):
        f = filedialog.askdirectory()
        if f:
            self.app.poky_path.set(f)
            self.save_poky_path()
            self.auto_load_config()

    def load_saved_path(self):
        try:
            if os.path.exists(self.app.config_file):
                with open(self.app.config_file, 'r') as f:
                    saved_path = f.read().strip()
                if saved_path and os.path.exists(saved_path):
                    self.app.poky_path.set(saved_path)
                    self.app.log(f"Loaded saved path: {saved_path}")
                    self.auto_load_config()
        except: pass
    
    def save_poky_path(self):
        try:
            path = self.app.poky_path.get()
            if path:
                with open(self.app.config_file, 'w') as f: f.write(path)
        except: pass

    def get_conf_path(self):
        return os.path.join(self.app.poky_path.get(), self.app.build_dir_name.get(), "conf", "local.conf")
    
    def get_tool_conf_path(self):
        return os.path.join(self.app.poky_path.get(), self.app.build_dir_name.get(), "conf", "yoctool.conf")

    def auto_load_config(self):
        self.load_config()

    def load_config(self):
        tool_conf = self.get_tool_conf_path()
        if not os.path.exists(tool_conf): 
            return

        try:
            with open(tool_conf, 'r') as f:
                state = json.load(f)
            
            self.app.tab_general.set_state(state.get("general", {}))
            self.app.tab_image.set_state(state.get("image", {}))
            self.app.tab_ota.set_state(state.get("ota", {}))
            
            mgr_states = state.get("managers", [])
            if mgr_states and len(mgr_states) > 0 and len(self.app.board_managers) > 0:
                self.app.board_managers[0].set_state(mgr_states[0])
            
            self.app.update_ui_visibility()
            self.app.log(f"App state loaded from {tool_conf}")

        except Exception as e:
            self.app.log(f"Error loading app state: {e}")

    def save_config(self):
        conf = self.get_conf_path()
        tool_conf = self.get_tool_conf_path()
        
        if not os.path.exists(os.path.dirname(conf)):
            messagebox.showerror("Error", "Build/conf directory not found. Please setup Poky first.")
            return

        try:
            if os.path.exists(conf):
                with open(conf, 'r') as f: lines = f.readlines()
            else:
                lines = []
            
            clean_lines = []
            skip_block = False
            for line in lines:
                if "# --- YOCTOOL AUTO CONFIG START" in line:
                    skip_block = True
                    continue
                if "# --- YOCTOOL AUTO CONFIG END" in line:
                    skip_block = False
                    continue
                if skip_block: continue
                # Skip existing vars to avoid duplicates
                if re.match(r'^\s*MACHINE\s*\?{0,2}=', line): continue
                if re.match(r'^\s*DISTRO\s*\?{0,2}=', line): continue
                if re.match(r'^\s*PACKAGE_CLASSES\s*\?{0,2}=', line): continue
                if re.match(r'^\s*BB_NUMBER_THREADS\s*=', line): continue
                if re.match(r'^\s*PARALLEL_MAKE\s*=', line): continue
                if re.match(r'^\s*EXTRA_IMAGE_FEATURES\s*\?{0,2}=', line): continue
                if re.match(r'^\s*DISTRO_FEATURES:append\s*=', line): continue
                if re.match(r'^\s*VIRTUAL-RUNTIME_init_manager\s*=', line): continue
                if re.match(r'^\s*INHERIT\s*\+=\s*"mender-full"', line): continue
                if re.match(r'^\s*MENDER_', line): continue
                clean_lines.append(line)

            if clean_lines and not clean_lines[-1].endswith('\n'):
                clean_lines[-1] += '\n'

            clean_lines.append("\n# --- YOCTOOL AUTO CONFIG START ---\n")
            clean_lines.extend(self.app.tab_general.get_config_lines())
            clean_lines.extend(self.app.tab_image.get_config_lines())

            for mgr in self.app.board_managers:
                if mgr.is_current_machine_supported():
                    clean_lines.extend(mgr.get_config_lines())

            clean_lines.extend(self.app.tab_ota.get_config_lines())
            clean_lines.append("# --- YOCTOOL AUTO CONFIG END ---\n")

            with open(conf, 'w') as f:
                f.writelines(clean_lines)

            self.regenerate_bblayers()

            app_state = {
                "general": self.app.tab_general.get_state(),
                "image": self.app.tab_image.get_state(),
                "ota": self.app.tab_ota.get_state(),
                "managers": [mgr.get_state() for mgr in self.app.board_managers]
            }
            
            with open(tool_conf, 'w') as f:
                json.dump(app_state, f, indent=4)

            self.app.log("Configuration saved to local.conf & yoctool.conf")
            messagebox.showinfo("Success", "Configuration Applied & Saved!")
            
        except Exception as e: messagebox.showerror("Error", str(e))

    def regenerate_bblayers(self):
        if not self.app.poky_path.get() or not self.app.build_dir_name.get(): return
        conf_dir = os.path.join(self.app.poky_path.get(), self.app.build_dir_name.get(), "conf")
        bblayers_conf = os.path.join(conf_dir, "bblayers.conf")
        
        base_content = [
            'POKY_BBLAYERS_CONF_VERSION = "2"',
            'BBPATH = "${TOPDIR}"',
            'BBFILES ?= ""',
            'BBLAYERS ?= " \\',
            '  ${TOPDIR}/../meta \\',
            '  ${TOPDIR}/../meta-poky \\',
            '  ${TOPDIR}/../meta-yocto-bsp \\',
            '"'
        ]
        
        os.makedirs(conf_dir, exist_ok=True)
        with open(bblayers_conf, 'w') as f:
            f.write('\n'.join(base_content) + '\n')
            
        self.app.log("Cleaned bblayers.conf (Factory Reset).")

        def append_layers_from(source):
            try:
                lines = source.get_bblayers_lines()
                with open(bblayers_conf, 'a') as f:
                    f.write('\n# Added by Yoctool\n')
                    for line in lines:
                        f.write(line)
            except: pass

        if self.app.active_manager:
            append_layers_from(self.app.active_manager)

        if hasattr(self.app.tab_ota, 'get_bblayers_lines'):
             append_layers_from(self.app.tab_ota)
             
        self.app.log("Regenerated bblayers.conf with correct paths.")

    def exec_stream_cmd(self, cmd_args, cwd=None):
        try:
            process = subprocess.Popen(cmd_args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, universal_newlines=True)
            for line in process.stdout:
                line = line.strip()
                if not line: continue
                if "%" in line: self.app.log_overwrite(line)
                else: self.app.log(line)
            process.wait()
            return process.returncode == 0
        except Exception as e:
            self.app.log(f"Error: {e}")
            return False

    # --- Git Cloning Logic ---
    def open_download_dialog(self):
        top = tk.Toplevel(self.app.root)
        top.title("Download Poky")
        top.geometry("500x350")
        ttk.Label(top, text="Select Badge/Branch:").pack(anchor="w", padx=10, pady=(10, 5))
        branch_var = tk.StringVar(value="Loading...")
        cb_branch = ttk.Combobox(top, textvariable=branch_var, values=[], state="readonly")
        cb_branch.pack(fill="x", padx=10)
        threading.Thread(target=self.scan_git_branches, args=(cb_branch, branch_var)).start()
        
        ttk.Label(top, text="Select Destination Parent Folder:").pack(anchor="w", padx=10, pady=(10, 5))
        dest_var = tk.StringVar(value=os.getcwd())
        f_dest = ttk.Frame(top)
        f_dest.pack(fill="x", padx=10)
        ttk.Entry(f_dest, textvariable=dest_var).pack(side="left", fill="x", expand=True)
        ttk.Button(f_dest, text="Browse", command=lambda: dest_var.set(filedialog.askdirectory() or dest_var.get())).pack(side="left", padx=5)
        
        self.lbl_dl_status = ttk.Label(top, text="Ready to clone...", foreground="blue")
        self.lbl_dl_status.pack(pady=(20, 5))
        self.pb_dl = ttk.Progressbar(top, mode="indeterminate")
        self.pb_dl.pack(fill="x", padx=20, pady=5)
        
        btn_start = ttk.Button(top, text="START DOWNLOAD", 
            command=lambda: self.start_clone_thread(top, branch_var.get(), dest_var.get(), btn_start))
        btn_start.pack(pady=20)

    def scan_git_branches(self, cb, var):
        try:
            cmd = "git ls-remote --heads git://git.yoctoproject.org/poky"
            proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if proc.returncode == 0:
                branches = []
                for line in proc.stdout.splitlines():
                    parts = line.split()
                    if len(parts) > 1:
                        ref = parts[1]
                        if ref.startswith("refs/heads/"):
                            b_name = ref.replace("refs/heads/", "")
                            if not b_name.endswith("-next"): branches.append(b_name)
                branches.sort(reverse=True)
                if "master" in branches: branches.remove("master"); branches.insert(0, "master")
                def update_cb():
                    cb['values'] = branches
                    if "scarthgap" in branches: var.set("scarthgap") 
                    elif branches: var.set(branches[0])
                    else: var.set("scarthgap")
                self.app.root.after(0, update_cb)
        except: pass

    def start_clone_thread(self, top, branch, parent_dir, btn):
        if not parent_dir or not os.path.exists(parent_dir): return
        target_dir = os.path.join(parent_dir, "poky")
        if os.path.exists(target_dir):
             if not messagebox.askyesno("Warning", f"Folder '{target_dir}' already exists. Clone?", parent=top): return
        btn.config(state="disabled")
        self.pb_dl.config(mode="determinate", value=0)
        self.lbl_dl_status.config(text=f"Cloning {branch} into {target_dir}...")
        threading.Thread(target=self.run_manual_clone, args=(top, branch, target_dir, btn)).start()

    def run_manual_clone(self, top, branch, target_dir, btn):
        try:
            cmd = f"git clone --progress -b {branch} git://git.yoctoproject.org/poky {shlex.quote(target_dir)}"
            process = subprocess.Popen(cmd, shell=True, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, universal_newlines=True)
            for line in process.stderr:
                text = line.strip()
                self.app.root.after(0, self.lbl_dl_status.config, {"text": text})
                match = re.search(r'(\d+)%', text)
                if match: self.app.root.after(0, self.pb_dl.config, {"value": int(match.group(1))})
            process.wait()
            
            if process.returncode == 0:
                self.app.root.after(0, self.app.poky_path.set, target_dir)
                self.app.root.after(0, self.save_poky_path)
                self.app.root.after(0, self.auto_load_config)
                self.app.root.after(0, messagebox.showinfo, "Success", "Poky cloned! Click 'Start Build' to fetch layers.", parent=top)
                self.app.root.after(0, top.destroy)
            else:
                self.app.root.after(0, messagebox.showerror, "Error", "Clone failed.", parent=top)
        except Exception as e: self.app.root.after(0, messagebox.showerror, "Error", str(e), parent=top)
        finally: self.app.root.after(0, lambda: btn.config(state="normal"))