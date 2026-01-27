import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
import re
import subprocess
import threading
import glob
import sys
import shlex
import json
import manager_rpi
import manager_update

class YoctoBuilderApp:
    def __init__(self, root):
        self.root = root
        
        # --- VERSION LOGIC ---
        # Get version dynamically from filename (e.g. YoctoTool_v1.0.0 -> v1.0.0)
        self.APP_VERSION = self.get_version_from_filename()
        
        self.root.title(f"Yocto Tool {self.APP_VERSION}")
        self.root.geometry("900x950")

        self.poky_path = tk.StringVar()
        self.build_dir_name = tk.StringVar(value="build")
        self.selected_drive = tk.StringVar()
        
        self.sudo_user = os.environ.get('SUDO_USER')
        if os.geteuid() != 0:
            messagebox.showwarning("Permission Warning", "Please run with 'sudo' to allow flashing.")
            if not self.sudo_user: self.sudo_user = os.environ.get('USER')
        if not self.sudo_user:
            self.sudo_user = "root"

        self.board_managers = [
            manager_rpi.RpiManager(self)
        ]
        self.active_manager = self.board_managers[0] 

        self.machine_var = tk.StringVar(value="raspberrypi0-wifi")
        self.image_var = tk.StringVar(value="core-image-full-cmdline")
        
        self.pkg_format_var = tk.StringVar(value="package_rpm")
        self.init_system_var = tk.StringVar(value="sysvinit")
        
        self.feat_debug_tweaks = tk.BooleanVar(value=True)
        self.feat_ssh_server = tk.BooleanVar(value=True)
        self.feat_tools_debug = tk.BooleanVar(value=False)
        
        self.build_progress = tk.DoubleVar()
        self.build_progress_text = tk.StringVar(value="0%")
        self.build_progress.trace_add("write", self._update_progress_canvas)
        
        self.config_file = os.path.expanduser("~/.yocto_tool_config")

        self.create_menu()
        self.create_widgets()
        self.load_saved_path()
        self.log(f"Tool running as root. Build user: {self.sudo_user}")

    def get_version_from_filename(self):
        # Default fallback for development
        version = "v1.0.0"
        
        # Check if running as compiled executable
        if getattr(sys, 'frozen', False):
            exe_name = os.path.basename(sys.executable)
            # Regex to find version in filename (e.g., YoctoTool_v1.0.0)
            match = re.search(r'YoctoTool_(v\d+\.\d+\.\d+)', exe_name)
            if match:
                version = match.group(1)
        
        return version

    def create_menu(self):
        menubar = tk.Menu(self.root)
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label=f"Version: {self.APP_VERSION}", state="disabled")
        help_menu.add_separator()
        help_menu.add_command(label="Check for Update...", command=self.check_update)
        help_menu.add_command(label="About", command=self.show_about)
        menubar.add_cascade(label="Help", menu=help_menu)
        self.root.config(menu=menubar)

    def check_update(self):
        manager_update.check_for_update(self.root, self.APP_VERSION)

    def show_about(self):
        messagebox.showinfo("About", f"Yocto Tool\nVersion: {self.APP_VERSION}\nAuthor: Hungnt8687")

    def create_widgets(self):
        self._setup_path_section()
        self._setup_config_section()
        self._setup_operations_section()
        self._setup_log_section()

    def _setup_path_section(self):
        frame_setup = ttk.LabelFrame(self.root, text="1. Project Setup")
        frame_setup.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(frame_setup, text="Poky Path:").grid(row=0, column=0, padx=5, pady=10, sticky="e")
        ttk.Entry(frame_setup, textvariable=self.poky_path, width=60).grid(row=0, column=1, padx=5, pady=10, sticky="ew")
        ttk.Button(frame_setup, text="Browse", command=self.browse_folder).grid(row=0, column=2, padx=5, pady=10)
        ttk.Button(frame_setup, text="Download Poky", command=self.open_download_dialog).grid(row=0, column=3, padx=5, pady=10)
        frame_setup.columnconfigure(1, weight=1)

    def _setup_config_section(self):
        frame_config = ttk.LabelFrame(self.root, text="2. Configuration")
        frame_config.pack(fill="x", padx=10, pady=5)
        
        notebook = ttk.Notebook(frame_config)
        notebook.pack(fill="both", expand=True, padx=5, pady=5)
        
        self._create_basic_tab(notebook)
        self._create_features_tab(notebook)
        
        for mgr in self.board_managers:
            mgr.create_tab(notebook)
        
        frame_cfg_btns = ttk.Frame(frame_config)
        frame_cfg_btns.pack(pady=10)
        self.btn_load = ttk.Button(frame_cfg_btns, text="LOAD", command=self.load_config)
        self.btn_load.pack(side="left", padx=10)
        self.btn_save = ttk.Button(frame_cfg_btns, text="SAVE", command=self.save_config)
        self.btn_save.pack(side="left", padx=10)
        
        self.update_ui_visibility()

    def update_ui_visibility(self, event=None):
        for mgr in self.board_managers:
            is_supported = mgr.is_current_machine_supported()
            mgr.set_visible(is_supported)
            if is_supported:
                self.active_manager = mgr

    def _create_basic_tab(self, notebook):
        tab_basic = ttk.Frame(notebook)
        notebook.add(tab_basic, text="Basic Settings")
        
        all_machines = ["qemux86-64"]
        for mgr in self.board_managers:
            all_machines.extend(mgr.machines)

        ttk.Label(tab_basic, text="MACHINE:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        self.machine_combo = ttk.Combobox(tab_basic, textvariable=self.machine_var, 
                                          values=all_machines, width=30)
        self.machine_combo.grid(row=0, column=1, padx=10, pady=10, sticky="w")
        self.machine_combo.bind("<<ComboboxSelected>>", self.update_ui_visibility)

        ttk.Label(tab_basic, text="IMAGE TARGET:").grid(row=1, column=0, padx=10, pady=10, sticky="e")
        self.image_combo = ttk.Combobox(tab_basic, textvariable=self.image_var, 
                                        values=["core-image-minimal", "core-image-base", "core-image-full-cmdline"], width=30)
        self.image_combo.grid(row=1, column=1, padx=10, pady=10, sticky="w")

    def _create_features_tab(self, notebook):
        tab_feat = ttk.Frame(notebook)
        notebook.add(tab_feat, text="Distro Features")
        
        ttk.Label(tab_feat, text="Package Format:").grid(row=0, column=0, padx=10, pady=5, sticky="w")
        ttk.OptionMenu(tab_feat, self.pkg_format_var, "package_rpm", "package_rpm", "package_deb", "package_ipk").grid(row=0, column=1, sticky="w")
        
        ttk.Label(tab_feat, text="Init System:").grid(row=0, column=2, padx=10, pady=5, sticky="w")
        ttk.OptionMenu(tab_feat, self.init_system_var, "sysvinit", "sysvinit", "systemd").grid(row=0, column=3, sticky="w")
        
        ttk.Label(tab_feat, text="Extra Features:").grid(row=1, column=0, padx=10, pady=5, sticky="nw")
        f_checks = ttk.Frame(tab_feat)
        f_checks.grid(row=1, column=1, columnspan=3, sticky="w")
        ttk.Checkbutton(f_checks, text="debug-tweaks", variable=self.feat_debug_tweaks).pack(anchor="w")
        ttk.Checkbutton(f_checks, text="ssh-server-openssh", variable=self.feat_ssh_server).pack(anchor="w")
        ttk.Checkbutton(f_checks, text="tools-debug", variable=self.feat_tools_debug).pack(anchor="w")

    def _setup_operations_section(self):
        frame_ops = ttk.Frame(self.root)
        frame_ops.pack(fill="x", padx=10, pady=5)
        frame_top = ttk.Frame(frame_ops)
        frame_top.pack(side="top", fill="x", expand=True)

        frame_build = ttk.LabelFrame(frame_top, text="3. Build Operations")
        frame_build.pack(side="left", fill="both", expand=True, padx=(0, 5))
        
        f_build_btns = ttk.Frame(frame_build)
        f_build_btns.pack(pady=15, padx=10)
        self.btn_build = ttk.Button(f_build_btns, text="START BUILD", command=self.start_build_thread)
        self.btn_build.pack(side="left", padx=10)
        self.btn_clean = ttk.Button(f_build_btns, text="CLEAN BUILD", command=self.start_clean_thread)
        self.btn_clean.pack(side="left", padx=10)

        frame_flash = ttk.LabelFrame(frame_top, text="4. Flash to SD Card")
        frame_flash.pack(side="left", fill="both", expand=True, padx=(5, 0))
        
        f_flash_ctrl = ttk.Frame(frame_flash)
        f_flash_ctrl.pack(pady=15, padx=10, fill="x")
        self.drive_menu = ttk.Combobox(f_flash_ctrl, textvariable=self.selected_drive, width=25, state="readonly")
        self.drive_menu.pack(side="left", padx=5, fill="x", expand=True)
        ttk.Button(f_flash_ctrl, text="↻", width=3, command=self.scan_drives).pack(side="left", padx=2)
        self.btn_flash = ttk.Button(f_flash_ctrl, text="FLASH", command=self.flash_image)
        self.btn_flash.pack(side="left", padx=10)

        frame_progress = ttk.Frame(frame_ops)
        frame_progress.pack(side="top", fill="x", padx=0, pady=(5, 10))
        self.pb_canvas = tk.Canvas(frame_progress, height=25, bg="#e0e0e0", highlightthickness=1, highlightbackground="#999")
        self.pb_canvas.pack(fill="x", expand=True)
        self.pb_rect = self.pb_canvas.create_rectangle(0, 0, 0, 25, fill="#4CAF50", outline="")
        self.pb_text = self.pb_canvas.create_text(0, 12, text="0%", font=("Arial", 10, "bold"), fill="black")
        self.pb_canvas.bind("<Configure>", lambda e: self._update_progress_canvas())

    def _update_progress_canvas(self, *args):
        try:
            percent = self.build_progress.get()
            percent = max(0, min(100, percent))
            canvas_width = self.pb_canvas.winfo_width()
            if canvas_width <= 1: canvas_width = 400
            bar_width = (canvas_width * percent) / 100
            self.pb_canvas.coords(self.pb_rect, 0, 0, bar_width, 25)
            self.pb_canvas.itemconfig(self.pb_text, text=f"{int(percent)}%")
            self.pb_canvas.coords(self.pb_text, canvas_width / 2, 12)
        except: pass

    def _setup_log_section(self):
        frame_log = ttk.LabelFrame(self.root, text="5. Terminal Log")
        frame_log.pack(fill="both", expand=True, padx=10, pady=5)
        self.log_area = scrolledtext.ScrolledText(frame_log, height=12, bg="black", fg="white", font=("Courier New", 10))
        self.log_area.pack(fill="both", expand=True, padx=5, pady=5)

    def log(self, msg):
        self.root.after(0, self._log_safe, msg)

    def _log_safe(self, msg):
        self.log_area.insert(tk.END, msg + "\n")
        self.log_area.see(tk.END)
    
    def log_overwrite(self, msg):
        self.root.after(0, self._log_overwrite_safe, msg)
    
    def _log_overwrite_safe(self, msg):
        self.log_area.delete("end-2l", "end-1l")
        self.log_area.insert(tk.END, msg + "\n")
        self.log_area.see(tk.END)

    def get_conf_path(self):
        return os.path.join(self.poky_path.get(), self.build_dir_name.get(), "conf", "local.conf")
    
    def get_tool_conf_path(self):
        return os.path.join(self.poky_path.get(), self.build_dir_name.get(), "conf", "yocto_tool.conf")

    def auto_load_config(self):
        self.load_config()

    def load_saved_path(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    saved_path = f.read().strip()
                if saved_path and os.path.exists(saved_path):
                    self.poky_path.set(saved_path)
                    self.log(f"Loaded saved path: {saved_path}")
                    self.auto_load_config()
        except: pass
    
    def save_poky_path(self):
        try:
            path = self.poky_path.get()
            if path:
                with open(self.config_file, 'w') as f: f.write(path)
        except: pass

    def browse_folder(self):
        f = filedialog.askdirectory()
        if f:
            self.poky_path.set(f)
            self.save_poky_path()
            self.auto_load_config()

    def load_config(self):
        tool_conf = self.get_tool_conf_path()
        if not os.path.exists(tool_conf): 
            return

        try:
            with open(tool_conf, 'r') as f:
                state = json.load(f)
            
            self.machine_var.set(state.get("machine", "raspberrypi0-wifi"))
            self.image_var.set(state.get("image", "core-image-full-cmdline"))
            self.pkg_format_var.set(state.get("pkg_format", "package_rpm"))
            self.init_system_var.set(state.get("init_system", "sysvinit"))
            
            feats = state.get("features", {})
            self.feat_debug_tweaks.set(feats.get("debug_tweaks", True))
            self.feat_ssh_server.set(feats.get("ssh_server", True))
            self.feat_tools_debug.set(feats.get("tools_debug", False))
            
            mgr_states = state.get("managers", [])
            if mgr_states and len(mgr_states) > 0 and len(self.board_managers) > 0:
                self.board_managers[0].set_state(mgr_states[0])
            
            self.update_ui_visibility()
            self.log(f"App state loaded from {tool_conf}")

        except Exception as e:
            self.log(f"Error loading app state: {e}")

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
                if "# --- YOCTO TOOL AUTO CONFIG START" in line:
                    skip_block = True
                    continue
                if "# --- YOCTO TOOL AUTO CONFIG END" in line:
                    skip_block = False
                    continue
                if skip_block: continue

                if re.match(r'^\s*MACHINE\s*\?{0,2}=', line): continue
                if re.match(r'^\s*PACKAGE_CLASSES\s*\?{0,2}=', line): continue
                if "ENABLE_UART" in line: continue
                
                clean_lines.append(line)

            if clean_lines and not clean_lines[-1].endswith('\n'):
                clean_lines[-1] += '\n'

            clean_lines.append(f'MACHINE ??= "{self.machine_var.get()}"\n')
            clean_lines.append(f'PACKAGE_CLASSES ?= "{self.pkg_format_var.get()}"\n')
            
            clean_lines.append("\n# --- YOCTO TOOL AUTO CONFIG START ---\n")
            
            if self.init_system_var.get() == "systemd":
                clean_lines.append('DISTRO_FEATURES:append = " systemd"\n')
                clean_lines.append('VIRTUAL-RUNTIME_init_manager = "systemd"\n')

            features = []
            if self.feat_debug_tweaks.get(): features.append("debug-tweaks")
            if self.feat_ssh_server.get(): features.append("ssh-server-openssh")
            if self.feat_tools_debug.get(): features.append("tools-debug")
            if features:
                clean_lines.append(f'EXTRA_IMAGE_FEATURES ?= "{" ".join(features)}"\n')
            
            for mgr in self.board_managers:
                if mgr.is_current_machine_supported():
                    clean_lines.extend(mgr.get_config_lines())
                    self.update_bblayers(mgr)

            clean_lines.append("# --- YOCTO TOOL AUTO CONFIG END ---\n")

            with open(conf, 'w') as f:
                f.writelines(clean_lines)

            app_state = {
                "machine": self.machine_var.get(),
                "image": self.image_var.get(),
                "pkg_format": self.pkg_format_var.get(),
                "init_system": self.init_system_var.get(),
                "features": {
                    "debug_tweaks": self.feat_debug_tweaks.get(),
                    "ssh_server": self.feat_ssh_server.get(),
                    "tools_debug": self.feat_tools_debug.get()
                },
                "managers": [mgr.get_state() for mgr in self.board_managers]
            }
            
            with open(tool_conf, 'w') as f:
                json.dump(app_state, f, indent=4)

            self.log("Configuration saved to local.conf & yocto_tool.conf")
            messagebox.showinfo("Success", "Configuration Applied & Saved!")
            
        except Exception as e: messagebox.showerror("Error", str(e))

    def update_bblayers(self, manager):
        bblayers_conf = os.path.join(self.poky_path.get(), self.build_dir_name.get(), "conf", "bblayers.conf")
        if not os.path.exists(bblayers_conf): return

        try:
            with open(bblayers_conf, 'r') as f: bb_content = f.read()
            
            lines_to_add = []
            required_lines = manager.get_bblayers_lines()
            
            needs_update = False
            for line in required_lines:
                key_part = line.split('/')[-1].replace('"\n', '').replace('"', '')
                if key_part not in bb_content:
                    lines_to_add.append(line)
                    needs_update = True
            
            if needs_update:
                with open(bblayers_conf, 'a') as f:
                    f.write('\n# Auto-added by Yocto Tool\n')
                    for line in lines_to_add:
                        f.write(line)
                self.log("Updated bblayers.conf")
        except Exception as e:
            self.log(f"Warning updating bblayers: {e}")

    def set_busy_state(self, busy):
        state = "disabled" if busy else "normal"
        self.btn_build.config(state=state)
        self.btn_clean.config(state=state)
        self.btn_flash.config(state=state)
        self.btn_load.config(state=state)
        self.btn_save.config(state=state)

    def exec_stream_cmd(self, cmd_args, cwd=None):
        try:
            process = subprocess.Popen(cmd_args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, universal_newlines=True)
            for line in process.stdout:
                line = line.strip()
                if not line: continue
                if "%" in line: self.log_overwrite(line)
                else: self.log(line)
            process.wait()
            return process.returncode == 0
        except Exception as e:
            self.log(f"Error: {e}")
            return False

    def check_and_download_layers(self):
        active_mgr = None
        for mgr in self.board_managers:
            if mgr.is_current_machine_supported():
                active_mgr = mgr
                break
        
        if not active_mgr: return

        poky = self.poky_path.get()
        if not poky or not os.path.isdir(poky): return

        required = active_mgr.get_required_layers()
        
        missing = []
        for name, url in required:
            if not os.path.exists(os.path.join(poky, name)):
                missing.append((name, url))

        if not missing: return

        self.log("Detecting missing layers...")
        try:
            branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=poky, text=True).strip()
            if branch == "HEAD": branch = "scarthgap"
        except: branch = "scarthgap"
        self.log(f"Detected Poky branch: {branch}")

        for name, url in missing:
            self.log(f"Cloning {name} ({branch})...")
            path = os.path.join(poky, name)
            success = self.exec_stream_cmd(["git", "clone", "--progress", "-b", branch, url, path])
            if not success:
                self.log(f"Failed to clone {name} ({branch}). Trying master...")
                self.exec_stream_cmd(["git", "clone", "--progress", url, path])

        self.log("Layer download check complete.")

    def run_build(self):
        try:
            self.check_and_download_layers()
            self.log(f"Building {self.image_var.get()}...")
            self.exec_user_cmd(f"bitbake {self.image_var.get()}")
        finally:
            self.root.after(0, self.set_busy_state, False)

    def start_build_thread(self):
        if not self.poky_path.get(): return
        self.set_busy_state(True)
        threading.Thread(target=self.run_build).start()

    def start_clean_thread(self):
        if not self.poky_path.get(): return
        if messagebox.askyesno("Confirm", "Clean build?"):
            self.set_busy_state(True)
            threading.Thread(target=self.run_clean).start()

    def run_clean(self):
        try:
            self.log("Cleaning...")
            self.exec_user_cmd(f"bitbake -c cleanall {self.image_var.get()}")
        finally:
            self.root.after(0, self.set_busy_state, False)

    def exec_user_cmd(self, cmd):
        safe_poky = shlex.quote(self.poky_path.get())
        safe_build = shlex.quote(self.build_dir_name.get())
        full_cmd = f"sudo -u {self.sudo_user} bash -c 'cd {safe_poky} && source oe-init-build-env {safe_build} && {cmd}'"
        
        proc = subprocess.Popen(full_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
        self.root.after(0, self.build_progress.set, 0)
        self.root.after(0, self.build_progress_text.set, "0%")
        
        while True:
            line = proc.stdout.readline()
            if not line and proc.poll() is not None: break
            if line:
                self.log(line.strip())
                m = re.search(r'Running task (\d+) of (\d+)', line)
                if m:
                    current = int(m.group(1))
                    total = int(m.group(2))
                    if total > 0:
                        percent = (current / total) * 100
                        self.root.after(0, self.build_progress.set, percent)
                        self.root.after(0, self.build_progress_text.set, f"{int(percent)}%")
                
        if proc.returncode == 0: 
            self.root.after(0, self.build_progress.set, 100)
            self.root.after(0, self.build_progress_text.set, "100%") 
            self.root.after(0, messagebox.showinfo, "Success", "Done!")
        else: 
            self.root.after(0, messagebox.showerror, "Error", "Failed!")

    def scan_drives(self):
        try:
            out = subprocess.check_output("lsblk -d -o NAME,SIZE,MODEL,TRAN -n", shell=True).decode()
            devs = [l for l in out.split('\n') if 'usb' in l or 'mmc' in l]
            self.drive_menu['values'] = devs if devs else ["No devices"]
            if devs: self.drive_menu.current(0)
        except: pass

    def flash_image(self):
        sel = self.selected_drive.get()
        if not sel or "No devices" in sel: return
        dev = f"/dev/{sel.split()[0]}"
        deploy = os.path.join(self.poky_path.get(), self.build_dir_name.get(), "tmp/deploy/images", self.machine_var.get())
        files = glob.glob(os.path.join(deploy, f"{self.image_var.get()}*.wic*"))
        if not files: 
            messagebox.showerror("Error", "No image found")
            return
        img = max(files, key=os.path.getctime)
        if messagebox.askyesno("Flash", f"Flash {os.path.basename(img)} to {dev}?"):
            self.set_busy_state(True)
            try: img_size = os.path.getsize(img)
            except: img_size = 0
            threading.Thread(target=self.run_flash, args=(img, dev, img_size)).start()

    def run_flash(self, img, dev, img_size):
        try:
            self.log("Flashing...")
            self.root.after(0, self.build_progress.set, 0)
            self.root.after(0, self.build_progress_text.set, "0%")
            
            subprocess.run(f"umount {shlex.quote(dev)}*", shell=True)
            safe_img = shlex.quote(img)
            safe_dev = shlex.quote(dev)
            
            if img.endswith(".bz2"): cmd = f"bzcat {safe_img} | dd of={safe_dev} bs=4M status=progress conv=fsync"
            else: cmd = f"dd if={safe_img} of={safe_dev} bs=4M status=progress conv=fsync"
            
            proc = subprocess.Popen(cmd, shell=True, stderr=subprocess.PIPE, universal_newlines=True)
            while True:
                line = proc.stderr.readline()
                if not line and proc.poll() is not None: break
                if "bytes" in line: 
                    self.log_overwrite(f">> {line.strip()}")
                    parts = line.split()
                    if parts and parts[0].isdigit() and img_size > 0:
                        bytes_copied = int(parts[0])
                        percent = (bytes_copied / img_size) * 100
                        percent = min(percent, 100)
                        self.root.after(0, self.build_progress.set, percent)
                        self.root.after(0, self.build_progress_text.set, f"{int(percent)}%")
            
            if proc.returncode == 0: 
                self.root.after(0, self.build_progress.set, 100)
                self.root.after(0, self.build_progress_text.set, "100%")
                self.root.after(0, messagebox.showinfo, "Success", "Flashed!")
        except Exception as e: 
            self.root.after(0, messagebox.showerror, "Error", str(e))
        finally: 
             self.root.after(0, self.set_busy_state, False)

    def open_download_dialog(self):
        top = tk.Toplevel(self.root)
        top.title("Download Poky (Yocto Project)")
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
                self.root.after(0, update_cb)
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
                self.root.after(0, self.lbl_dl_status.config, {"text": text})
                match = re.search(r'(\d+)%', text)
                if match: self.root.after(0, self.pb_dl.config, {"value": int(match.group(1))})
            process.wait()
            
            if process.returncode == 0:
                self.root.after(0, self.poky_path.set, target_dir)
                self.root.after(0, self.save_poky_path)
                self.root.after(0, self.auto_load_config)
                self.root.after(0, messagebox.showinfo, "Success", "Poky cloned! Click 'Start Build' to fetch layers.", parent=top)
                self.root.after(0, top.destroy)
            else:
                self.root.after(0, messagebox.showerror, "Error", "Clone failed.", parent=top)
        except Exception as e: self.root.after(0, messagebox.showerror, "Error", str(e), parent=top)
        finally: self.root.after(0, lambda: btn.config(state="normal"))

if __name__ == "__main__":
    if os.geteuid() != 0:
        try:
            subprocess.check_call(["sudo", sys.executable] + sys.argv)
        except subprocess.CalledProcessError:
            pass
        sys.exit(0)

    root = tk.Tk()
    app = YoctoBuilderApp(root)
    root.mainloop()