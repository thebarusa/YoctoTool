import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
import re
import subprocess
import threading
import glob
import sys
import shlex
import manager_rpi

class YoctoBuilderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Yocto Tool v14 (Fix Extra Space Issue)")
        self.root.geometry("900x950")

        # --- Variables ---
        self.poky_path = tk.StringVar()
        self.build_dir_name = tk.StringVar(value="build")
        self.selected_drive = tk.StringVar()
        
        # 1. Detect Real User (SUDO_USER)
        self.sudo_user = os.environ.get('SUDO_USER')
        if os.geteuid() != 0:
            messagebox.showwarning("Permission Warning", "Please run with 'sudo' to allow flashing.")
            if not self.sudo_user: self.sudo_user = os.environ.get('USER')
        if not self.sudo_user:
            messagebox.showerror("Error", "Could not detect SUDO_USER.")
            sys.exit(1)

        # --- Config Variables ---
        self.machine_var = tk.StringVar(value="raspberrypi0-wifi")
        self.image_var = tk.StringVar(value="core-image-full-cmdline")
        
        # Advanced Options
        self.pkg_format_var = tk.StringVar(value="package_rpm")
        self.init_system_var = tk.StringVar(value="sysvinit")
        
        # Checkboxes
        self.feat_debug_tweaks = tk.BooleanVar(value=True)
        self.feat_ssh_server = tk.BooleanVar(value=True)
        self.feat_tools_debug = tk.BooleanVar(value=False)
        
        # RPi Manager
        self.rpi_manager = manager_rpi.RpiManager(self)

        self.create_widgets()
        self.log(f"Tool running as root. Build user: {self.sudo_user}")
        self.log(f"Tool running as root. Build user: {self.sudo_user}")

    def create_widgets(self):
        self._setup_path_section()
        self._setup_config_section()
        self._setup_operations_section() # Combined Build + Flash
        self._setup_log_section()

    def _setup_path_section(self):
        # Frame 1: Setup
        frame_setup = ttk.LabelFrame(self.root, text="1. Project Setup")
        frame_setup.pack(fill="x", padx=10, pady=5)
        
        # Grid layout for better alignment
        ttk.Label(frame_setup, text="Poky Path:").grid(row=0, column=0, padx=5, pady=10, sticky="e")
        ttk.Entry(frame_setup, textvariable=self.poky_path, width=60).grid(row=0, column=1, padx=5, pady=10, sticky="ew")
        ttk.Entry(frame_setup, textvariable=self.poky_path, width=60).grid(row=0, column=1, padx=5, pady=10, sticky="ew")
        ttk.Button(frame_setup, text="Browse", command=self.browse_folder).grid(row=0, column=2, padx=5, pady=10)
        ttk.Button(frame_setup, text="Download Poky", command=self.open_download_dialog).grid(row=0, column=3, padx=5, pady=10)
        
        frame_setup.columnconfigure(1, weight=1)

    def _setup_config_section(self):
        frame_config = ttk.LabelFrame(self.root, text="2. Configuration (local.conf)")
        frame_config.pack(fill="x", padx=10, pady=5)
        
        notebook = ttk.Notebook(frame_config)
        notebook.pack(fill="both", expand=True, padx=5, pady=5)
        
        self._create_basic_tab(notebook)
        self._create_features_tab(notebook)
        self.rpi_manager.create_tab(notebook)
        
        # Buttons
        frame_cfg_btns = ttk.Frame(frame_config)
        frame_cfg_btns.pack(pady=10)
        self.btn_load = ttk.Button(frame_cfg_btns, text="LOAD CONFIG", command=self.load_config)
        self.btn_load.pack(side="left", padx=10)
        self.btn_save = ttk.Button(frame_cfg_btns, text="SAVE CONFIG", command=self.save_config)
        self.btn_save.pack(side="left", padx=10)
        
        # Initial visibility check
        self.update_ui_visibility()

    def update_ui_visibility(self, event=None):
        machine = self.machine_var.get()
        is_rpi = "raspberrypi" in machine
        self.rpi_manager.set_visible(is_rpi)

    def _create_basic_tab(self, notebook):
        tab_basic = ttk.Frame(notebook)
        notebook.add(tab_basic, text="Basic Settings")
        
        ttk.Label(tab_basic, text="MACHINE:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        self.machine_combo = ttk.Combobox(tab_basic, textvariable=self.machine_var, 
                                          values=["raspberrypi0-wifi", "raspberrypi3", "raspberrypi4", "qemux86-64"], width=30)
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
        # Combined Operations Frame
        frame_ops = ttk.Frame(self.root)
        frame_ops.pack(fill="x", padx=10, pady=5)

        # Left: Build
        frame_build = ttk.LabelFrame(frame_ops, text="3. Build Operations")
        frame_build.pack(side="left", fill="both", expand=True, padx=(0, 5))
        
        f_build_btns = ttk.Frame(frame_build)
        f_build_btns.pack(pady=15, padx=10)
        self.btn_build = ttk.Button(f_build_btns, text="START BUILD", command=self.start_build_thread)
        self.btn_build.pack(side="left", padx=10)
        self.btn_clean = ttk.Button(f_build_btns, text="CLEAN BUILD", command=self.start_clean_thread)
        self.btn_clean.pack(side="left", padx=10)

        # Right: Flash
        frame_flash = ttk.LabelFrame(frame_ops, text="4. Flash to SD Card")
        frame_flash.pack(side="left", fill="both", expand=True, padx=(5, 0))
        
        f_flash_ctrl = ttk.Frame(frame_flash)
        f_flash_ctrl.pack(pady=15, padx=10, fill="x")
        
        self.drive_menu = ttk.Combobox(f_flash_ctrl, textvariable=self.selected_drive, width=25, state="readonly")
        self.drive_menu.pack(side="left", padx=5, fill="x", expand=True)
        
        ttk.Button(f_flash_ctrl, text="↻", width=3, command=self.scan_drives).pack(side="left", padx=2)
        self.btn_flash = ttk.Button(f_flash_ctrl, text="FLASH", command=self.flash_image)
        self.btn_flash.pack(side="left", padx=10)

    # Legacy separate setup methods removed/merged above

    def _setup_log_section(self):
        frame_log = ttk.LabelFrame(self.root, text="5. Terminal Log")
        frame_log.pack(fill="both", expand=True, padx=10, pady=5)
        self.log_area = scrolledtext.ScrolledText(frame_log, height=12, bg="black", fg="white", font=("Courier New", 10))
        self.log_area.pack(fill="both", expand=True, padx=5, pady=5)

    # --- HELPERS ---
    # --- HELPERS ---
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

    def browse_folder(self):
        f = filedialog.askdirectory()
        if f: self.poky_path.set(f)

    def get_conf_path(self):
        return os.path.join(self.poky_path.get(), self.build_dir_name.get(), "conf", "local.conf")



    # --- LOAD CONFIG ---
    def load_config(self):
        conf = self.get_conf_path()
        if not os.path.exists(conf):
            messagebox.showerror("Error", f"Missing {conf}")
            return
        
        try:
            with open(conf, 'r') as f: content = f.read()
            
            m = re.search(r'^\s*MACHINE\s*\?{0,2}=\s*"(.*?)"', content, re.MULTILINE)
            if m: self.machine_var.set(m.group(1))

            m = re.search(r'^\s*PACKAGE_CLASSES\s*\?{0,2}=\s*"(.*?)"', content, re.MULTILINE)
            if m: self.pkg_format_var.set(m.group(1).split()[0])

            self.feat_debug_tweaks.set("debug-tweaks" in content)
            self.feat_ssh_server.set("ssh-server-openssh" in content or "openssh" in content)
            self.feat_tools_debug.set("tools-debug" in content)            
            self.rpi_manager.parse_config(content)
            self.update_ui_visibility() # Update tabs based on loaded machine

            self.log(f"Config loaded from {conf}")
        except Exception as e: messagebox.showerror("Error", str(e))

    # --- SAVE CONFIG (FIXED SPACE ISSUE) ---
    def save_config(self):
        conf = self.get_conf_path()
        if not os.path.exists(conf): return
        
        try:
            with open(conf, 'r') as f: lines = f.readlines()
            
            clean_lines = []
            skip_block = False

            # --- STEP 1: CLEAN ORPHANS ---
            for line in lines:
                if "# --- YOCTO TOOL AUTO CONFIG START" in line:
                    skip_block = True
                    continue
                if "# --- YOCTO TOOL AUTO CONFIG END" in line:
                    skip_block = False
                    continue
                if skip_block:
                    continue

                if "RPI_EXTRA_CONFIG" in line and "dtoverlay=dwc2" in line: continue
                if "KERNEL_MODULE_AUTOLOAD" in line and "dwc2 g_ether" in line: continue
                if "WIFI_SSID" in line or "WIFI_PASSWORD" in line: continue
                if "LICENSE_FLAGS_ACCEPTED" in line and "synaptics-killswitch" in line: continue
                if "ENABLE_UART" in line: continue
                if "IMAGE_INSTALL" in line and "kernel-module-dwc2" in line: continue
                if "IMAGE_INSTALL" in line and "wpa-supplicant" in line and "rpidistro-bcm43430" in line: continue
                if re.match(r'^\s*MACHINE\s*\?{0,2}=', line): continue
                if re.match(r'^\s*PACKAGE_CLASSES\s*\?{0,2}=', line): continue

                clean_lines.append(line)

            # --- STEP 2: WRITE NEW CONFIG ---
            
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
            
            # Only apply RPi specific settings if we are targeting a Raspberry Pi
            is_rpi = "raspberrypi" in self.machine_var.get()
            
            if is_rpi:
                 # 4. Delegate config generation to RpiManager.
                 clean_lines.extend(self.rpi_manager.get_config_lines())

            clean_lines.append("# --- YOCTO TOOL AUTO CONFIG END ---\n")

            with open(conf, 'w') as f:
                f.writelines(clean_lines)
            
            self.log("Configuration saved (Space issue fixed).")
            messagebox.showinfo("Success", "Configuration Fixed & Updated!")
            
        except Exception as e: messagebox.showerror("Error", str(e))

    # --- BUSY STATE ---
    def set_busy_state(self, busy):
        state = "disabled" if busy else "normal"
        self.btn_build.config(state=state)
        self.btn_clean.config(state=state)
        self.btn_flash.config(state=state)
        self.btn_load.config(state=state)
        self.btn_save.config(state=state)

    # --- BUILD & FLASH ---
    def start_build_thread(self):
        if not self.poky_path.get(): return
        self.set_busy_state(True)
        threading.Thread(target=self.run_build).start()

    def start_clean_thread(self):
        if not self.poky_path.get(): return
        if messagebox.askyesno("Confirm", "Clean build?"):
            self.set_busy_state(True)
            threading.Thread(target=self.run_clean).start()

    def run_build(self):
        try:
            self.log(f"Building {self.image_var.get()}...")
            self.exec_user_cmd(f"bitbake {self.image_var.get()}")
        finally:
            self.root.after(0, self.set_busy_state, False)

    def run_clean(self):
        try:
            self.log("Cleaning...")
            self.exec_user_cmd(f"bitbake -c cleanall {self.image_var.get()}")
        finally:
            self.root.after(0, self.set_busy_state, False)

    def exec_user_cmd(self, cmd):
        # Use shlex for quoting path components to be safe
        safe_poky = shlex.quote(self.poky_path.get())
        safe_build = shlex.quote(self.build_dir_name.get())
        
        # We generally construct the full bash command string since we are passing it to 'bash -c'
        # Quoting the inner command is tricky, but basically we want:
        # sudo -u user bash -c 'cd quoted_path && source oe-init... quoted_build && ...'
        
        full_cmd = f"sudo -u {self.sudo_user} bash -c 'cd {safe_poky} && source oe-init-build-env {safe_build} && {cmd}'"
        
        # Using shell=True here is necessary because we are invoking a complex bash command.
        # safe_poky/safe_build help mitigate injection if they contained malicious shell chars.
        
        proc = subprocess.Popen(full_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
        
        # Read stdout safely
        while True:
            line = proc.stdout.readline()
            if not line and proc.poll() is not None:
                break
            if line:
                self.log(line.strip())
                
        if proc.returncode == 0: 
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
            threading.Thread(target=self.run_flash, args=(img, dev)).start() # Fixed: removed btn_flash disabling here, handled in busy state

    def run_flash(self, img, dev):
        try:
            self.log("Flashing...")
            # Unmount all partitions from that device
            subprocess.run(f"umount {shlex.quote(dev)}*", shell=True)
            
            # Construct dd command safely
            safe_img = shlex.quote(img)
            safe_dev = shlex.quote(dev)
            
            if img.endswith(".bz2"):
                cmd = f"bzcat {safe_img} | dd of={safe_dev} bs=4M status=progress conv=fsync"
            else:
                cmd = f"dd if={safe_img} of={safe_dev} bs=4M status=progress conv=fsync"
            
            proc = subprocess.Popen(cmd, shell=True, stderr=subprocess.PIPE, universal_newlines=True)
            while True:
                line = proc.stderr.readline()
                if not line and proc.poll() is not None: break
                if "bytes" in line: 
                    # send to main thread
                    self.log_overwrite(f">> {line.strip()}")
            
            if proc.returncode == 0: 
                self.root.after(0, messagebox.showinfo, "Success", "Flashed!")
        except Exception as e: 
            self.root.after(0, messagebox.showerror, "Error", str(e))
        finally: 
             self.root.after(0, self.set_busy_state, False)

    # --- DOWNLOAD POKY FEATURE ---
    def open_download_dialog(self):
        top = tk.Toplevel(self.root)
        top.title("Download Poky (Yocto Project)")
        top.geometry("500x350")
        
        # Branch Selection
        ttk.Label(top, text="Select Badge/Branch:").pack(anchor="w", padx=10, pady=(10, 5))
        branch_var = tk.StringVar(value="Loading...")
        cb_branch = ttk.Combobox(top, textvariable=branch_var, values=[], state="readonly")
        cb_branch.pack(fill="x", padx=10)
        
        # Start scanning branches in background
        threading.Thread(target=self.scan_git_branches, args=(cb_branch, branch_var)).start()
        
        # Parent Directory Selection
        ttk.Label(top, text="Select Destination Parent Folder:").pack(anchor="w", padx=10, pady=(10, 5))
        # Default to current directory as requested
        dest_var = tk.StringVar(value=os.getcwd())
        
        f_dest = ttk.Frame(top)
        f_dest.pack(fill="x", padx=10)
        ttk.Entry(f_dest, textvariable=dest_var).pack(side="left", fill="x", expand=True)
        ttk.Button(f_dest, text="Browse", command=lambda: dest_var.set(filedialog.askdirectory() or dest_var.get())).pack(side="left", padx=5)
        
        # Progress
        self.lbl_dl_status = ttk.Label(top, text="Ready to clone...", foreground="blue")
        self.lbl_dl_status.pack(pady=(20, 5))
        
        self.pb_dl = ttk.Progressbar(top, mode="indeterminate")
        self.pb_dl.pack(fill="x", padx=20, pady=5)
        
        # Start Button
        btn_start = ttk.Button(top, text="START DOWNLOAD", 
            command=lambda: self.start_clone_thread(top, branch_var.get(), dest_var.get(), btn_start))
        btn_start.pack(pady=20)

    def scan_git_branches(self, cb, var):
        try:
            # Use git ls-remote to find heads
            cmd = "git ls-remote --heads git://git.yoctoproject.org/poky"
            proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            if proc.returncode == 0:
                branches = []
                for line in proc.stdout.splitlines():
                    # Format: <hash> refs/heads/<branch>
                    parts = line.split()
                    if len(parts) > 1:
                        ref = parts[1]
                        if ref.startswith("refs/heads/"):
                            b_name = ref.replace("refs/heads/", "")
                            # Filter out unlikely branches if needed, or just keep all
                            if not b_name.endswith("-next"): # Optional cleanup
                                branches.append(b_name)
                
                # Sort: master first, then others reverse alphabetical (usually newer releases first) or just alphabetical
                branches.sort(reverse=True)
                if "master" in branches:
                    branches.remove("master")
                    branches.insert(0, "master") # Ensure master is top
                
                def update_cb():
                    cb['values'] = branches
                    if "scarthgap" in branches:
                        var.set("scarthgap") 
                    elif branches:
                        var.set(branches[0])
                    else:
                        var.set("scarthgap") # Fallback
                        
                self.root.after(0, update_cb)
            else:
                # Fallback on failure
                self.root.after(0, lambda: cb.config(values=["scarthgap", "kirkstone", "dunfell", "master"]))
                self.root.after(0, lambda: var.set("scarthgap"))
        except:
             pass

    def start_clone_thread(self, top, branch, parent_dir, btn):
        if not parent_dir or not os.path.exists(parent_dir):
            messagebox.showerror("Error", "Invalid destination folder", parent=top)
            return
            
        target_dir = os.path.join(parent_dir, "poky")
        if os.path.exists(target_dir):
             if not messagebox.askyesno("Warning", f"Folder '{target_dir}' already exists. Clone anyway (might fail)?", parent=top):
                 return

        btn.config(state="disabled")
        self.pb_dl.config(mode="determinate", value=0) # Switch to determinate
        self.lbl_dl_status.config(text=f"Cloning {branch} into {target_dir}...")
        
        threading.Thread(target=self.run_clone, args=(top, branch, target_dir, btn)).start()

    def run_clone(self, top, branch, target_dir, btn):
        try:
            cmd = f"git clone --progress -b {branch} git://git.yoctoproject.org/poky {shlex.quote(target_dir)}"
            
            process = subprocess.Popen(
                cmd, 
                shell=True, 
                stderr=subprocess.PIPE, 
                stdout=subprocess.DEVNULL,
                universal_newlines=True
            )

            # Git prints progress to stderr
            for line in process.stderr:
                self.root.after(0, self.lbl_dl_status.config, {"text": f"{line.strip()}"})
                
                # Regex to catch percentage, e.g. "Receiving objects:  12% (123/456)"
                match = re.search(r'(\d+)%', line)
                if match:
                    percent = int(match.group(1))
                    self.root.after(0, self.pb_dl.config, {"value": percent})

            process.wait()
            
            if process.returncode == 0:
                self.root.after(0, self.lbl_dl_status.config, {"text": "Download Complete!", "foreground": "green"})
                self.root.after(0, self.pb_dl.config, {"value": 100})
                self.root.after(0, self.poky_path.set, target_dir)
                self.root.after(0, messagebox.showinfo, "Success", f"Successfully cloned Poky ({branch})!", parent=top)
                self.root.after(0, top.destroy)
            else:
                self.root.after(0, self.lbl_dl_status.config, {"text": "Download Failed!", "foreground": "red"})
                self.root.after(0, messagebox.showerror, "Error", "Clone failed! Check logs.", parent=top)
                
        except Exception as e:
            self.root.after(0, messagebox.showerror, "Error", str(e), parent=top)
        finally:
            self.root.after(0, lambda: btn.config(state="normal"))

if __name__ == "__main__":
    root = tk.Tk()
    app = YoctoBuilderApp(root)
    root.mainloop()