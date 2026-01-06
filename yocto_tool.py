import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
import re
import subprocess
import threading
import glob
import sys

class YoctoBuilderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Yocto Tool v8 (Fix BitBake Root Error)")
        self.root.geometry("900x850")

        # Variables
        self.poky_path = tk.StringVar()
        self.build_dir_name = tk.StringVar(value="build")
        self.machine_var = tk.StringVar(value="raspberrypi0-wifi")
        self.image_var = tk.StringVar(value="core-image-full-cmdline")
        self.selected_drive = tk.StringVar()
        
        # 1. Detect Real User (User who called sudo)
        self.sudo_user = os.environ.get('SUDO_USER')
        
        # Check Root
        if os.geteuid() != 0:
            messagebox.showwarning("Permission Warning", "Please run this tool with 'sudo' to allow flashing.")
            # Fallback if not root (for testing UI)
            if not self.sudo_user: self.sudo_user = os.environ.get('USER')
        
        if not self.sudo_user:
            messagebox.showerror("Error", "Could not detect the original user (SUDO_USER).")
            sys.exit(1)

        self.create_widgets()
        self.log(f"Tool running as root. Build commands will run as user: {self.sudo_user}")

    def create_widgets(self):
        # --- Section 1: Project Setup ---
        frame_setup = ttk.LabelFrame(self.root, text="1. Yocto Project Location")
        frame_setup.pack(fill="x", padx=10, pady=5)

        ttk.Label(frame_setup, text="Poky Root Path:").grid(row=0, column=0, padx=5, pady=5)
        ttk.Entry(frame_setup, textvariable=self.poky_path, width=50).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(frame_setup, text="Browse", command=self.browse_folder).grid(row=0, column=2, padx=5, pady=5)
        ttk.Button(frame_setup, text="Load Config", command=self.load_config).grid(row=0, column=3, padx=5, pady=5)

        # --- Section 2: Configuration ---
        frame_config = ttk.LabelFrame(self.root, text="2. Configuration (local.conf)")
        frame_config.pack(fill="x", padx=10, pady=5)

        # Machine Selection
        ttk.Label(frame_config, text="MACHINE:").grid(row=0, column=0, padx=5, pady=5)
        machine_options = [
            "raspberrypi0-wifi", "raspberrypi0-2w-64", "raspberrypi3", 
            "raspberrypi4", "raspberrypi4-64", "qemux86-64", "qemuarm"
        ]
        self.machine_combo = ttk.Combobox(frame_config, textvariable=self.machine_var, values=machine_options, width=27)
        self.machine_combo.grid(row=0, column=1, padx=5, pady=5)

        # Image Selection
        ttk.Label(frame_config, text="IMAGE TARGET:").grid(row=0, column=2, padx=5, pady=5)
        common_targets = [
            "core-image-minimal", "core-image-base", "core-image-full-cmdline",
            "core-image-sato", "core-image-weston", "meta-toolchain"
        ]
        self.image_combo = ttk.Combobox(frame_config, textvariable=self.image_var, values=common_targets, width=27)
        self.image_combo.grid(row=0, column=3, padx=5, pady=5)
        
        ttk.Button(frame_config, text="Save Config", command=self.save_config).grid(row=0, column=4, padx=5, pady=5)

        # --- Section 3: Build Actions ---
        frame_build = ttk.LabelFrame(self.root, text="3. Build Actions (Runs as User)")
        frame_build.pack(fill="x", padx=10, pady=5)

        btn_build = ttk.Button(frame_build, text="START BUILD", command=self.start_build_thread)
        btn_build.pack(side="left", padx=20, pady=10, expand=True)

        btn_clean = ttk.Button(frame_build, text="CLEAN BUILD", command=self.start_clean_thread)
        btn_clean.pack(side="right", padx=20, pady=10, expand=True)

        # --- Section 4: Flash ---
        frame_flash = ttk.LabelFrame(self.root, text="4. Flash to SD Card (Runs as Root)")
        frame_flash.pack(fill="x", padx=10, pady=5)

        self.drive_menu = ttk.Combobox(frame_flash, textvariable=self.selected_drive, width=40, state="readonly")
        self.drive_menu.pack(side="left", padx=10, pady=15)
        
        ttk.Button(frame_flash, text="Refresh Drives", command=self.scan_drives).pack(side="left", padx=5, pady=15)

        self.btn_flash = ttk.Button(frame_flash, text="FORMAT & FLASH", command=self.flash_image)
        self.btn_flash.pack(side="left", padx=20, pady=15)

        # --- Section 5: Terminal Log ---
        frame_log = ttk.LabelFrame(self.root, text="5. Terminal Log")
        frame_log.pack(fill="both", expand=True, padx=10, pady=10)

        self.log_area = scrolledtext.ScrolledText(
            frame_log, height=15, state='disabled', 
            bg="#000000", fg="#FFFFFF", insertbackground="white", 
            font=("Courier New", 10, "bold")
        )
        self.log_area.pack(fill="both", expand=True, padx=5, pady=5)

    # --- LOGGING HELPERS ---
    def log(self, message):
        self.log_area.config(state='normal')
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)
        self.log_area.config(state='disabled')

    def log_overwrite_last_line(self, message):
        self.log_area.config(state='normal')
        self.log_area.delete("end-2l", "end-1l") 
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)
        self.log_area.config(state='disabled')

    # --- CONFIGURATION FUNCTIONS ---
    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder: self.poky_path.set(folder)

    def get_conf_path(self):
        return os.path.join(self.poky_path.get(), self.build_dir_name.get(), "conf", "local.conf")

    def load_config(self):
        conf = self.get_conf_path()
        if not os.path.exists(conf):
            messagebox.showerror("Error", f"Could not find {conf}")
            return
        try:
            with open(conf, 'r') as f: content = f.read()
            match = re.search(r'^\s*MACHINE\s*\?{1,2}=\s*"(.*?)"', content, re.MULTILINE)
            if match: self.machine_var.set(match.group(1))
            self.log(f"Loaded config: MACHINE={self.machine_var.get()}")
        except Exception as e: messagebox.showerror("Error", str(e))

    def save_config(self):
        conf = self.get_conf_path()
        if not os.path.exists(conf): return
        new_m = self.machine_var.get()
        try:
            with open(conf, 'r') as f: lines = f.readlines()
            with open(conf, 'w') as f:
                updated = False
                for line in lines:
                    if re.match(r'^\s*MACHINE\s*\?{1,2}=', line):
                        f.write(f'MACHINE ??= "{new_m}"\n')
                        updated = True
                    else: f.write(line)
                if not updated: f.write(f'\nMACHINE ??= "{new_m}"\n')
            self.log(f"Saved MACHINE={new_m}")
            messagebox.showinfo("Success", "Config saved!")
        except Exception as e: messagebox.showerror("Error", str(e))

    # --- BUILD FUNCTIONS (UPDATED TO DROP ROOT) ---
    def start_build_thread(self):
        if not self.poky_path.get():
            messagebox.showerror("Error", "Select Poky folder first.")
            return
        threading.Thread(target=self.run_build).start()

    def start_clean_thread(self):
        if not self.poky_path.get():
            messagebox.showerror("Error", "Select Poky folder first.")
            return
        confirm = messagebox.askyesno("Confirm Clean", "Clean build files (bitbake -c cleanall)?")
        if confirm:
            threading.Thread(target=self.run_clean).start()

    def run_build(self):
        self.log(f"--- STARTING BUILD (as user: {self.sudo_user}) ---")
        # Command to run INSIDE the user shell
        inner_cmd = f"source oe-init-build-env {self.build_dir_name.get()} && bitbake {self.image_var.get()}"
        self.execute_as_user(inner_cmd)

    def run_clean(self):
        self.log(f"--- CLEANING BUILD (as user: {self.sudo_user}) ---")
        inner_cmd = f"source oe-init-build-env {self.build_dir_name.get()} && bitbake -c cleanall {self.image_var.get()}"
        self.execute_as_user(inner_cmd)

    def execute_as_user(self, inner_cmd):
        # We construct a command that:
        # 1. Uses 'sudo -u <user>' to switch from root back to normal user
        # 2. Opens a bash shell
        # 3. Changes directory to Poky folder
        # 4. Executes the Yocto commands
        
        # Note: We use 'bash -c' to wrap the whole command string
        full_cmd = f"sudo -u {self.sudo_user} bash -c 'cd {self.poky_path.get()} && {inner_cmd}'"
        
        proc = subprocess.Popen(
            full_cmd, 
            shell=True,
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, 
            universal_newlines=True
        )
        
        for line in proc.stdout: 
            self.log(line.strip())
        
        proc.wait()
        
        if proc.returncode == 0:
            self.log("--- OPERATION SUCCESSFUL ---")
            messagebox.showinfo("Success", "Operation Completed Successfully!")
        else:
            self.log("--- OPERATION FAILED ---")
            messagebox.showerror("Error", "Operation Failed. Check logs.")

    # --- FLASH FUNCTIONS (RUNS AS ROOT) ---
    def scan_drives(self):
        try:
            cmd = "lsblk -d -o NAME,SIZE,MODEL,TRAN -n"
            out = subprocess.check_output(cmd, shell=True).decode()
            devs = [line for line in out.split('\n') if 'usb' in line or 'mmc' in line]
            if not devs: devs = ["No removable devices found"]
            self.drive_menu['values'] = devs
            if devs: self.drive_menu.current(0)
        except Exception as e: self.log(f"Scan error: {e}")

    def flash_image(self):
        # Flashing NEEDS root, so we just run normally since the app is already sudo
        sel = self.selected_drive.get()
        if not sel or "No removable" in sel:
            messagebox.showerror("Error", "Select a drive.")
            return
        
        dev_path = f"/dev/{sel.split()[0]}"
        deploy_dir = os.path.join(self.poky_path.get(), self.build_dir_name.get(), "tmp/deploy/images", self.machine_var.get())
        
        # Find image
        pattern_bz2 = os.path.join(deploy_dir, f"{self.image_var.get()}*.wic.bz2")
        pattern_wic = os.path.join(deploy_dir, f"{self.image_var.get()}*.wic")
        
        files = glob.glob(pattern_bz2) + glob.glob(pattern_wic)
        if not files:
            messagebox.showerror("Error", "No image found.")
            return

        latest_image = max(files, key=os.path.getctime)
        
        confirm = messagebox.askyesno("Confirm", f"ERASE ALL DATA on {dev_path}?\nImage: {os.path.basename(latest_image)}")
        if confirm:
            self.btn_flash.config(state="disabled")
            threading.Thread(target=self.run_flash, args=(latest_image, dev_path)).start()

    def run_flash(self, image_file, device_path):
        try:
            self.log(f"--- FLASHING STARTED (as ROOT) ---")
            self.log(f"Image: {os.path.basename(image_file)}")
            self.log("Unmounting drives...")
            subprocess.run(f"umount {device_path}*", shell=True)

            self.log("Writing image... (Please wait)")

            if image_file.endswith(".bz2"):
                cmd = f"bzcat {image_file} | dd of={device_path} bs=4M status=progress conv=fsync"
            else:
                cmd = f"dd if={image_file} of={device_path} bs=4M status=progress conv=fsync"

            proc = subprocess.Popen(cmd, shell=True, stderr=subprocess.PIPE, universal_newlines=True)
            
            last_was_progress = False

            while True:
                line = proc.stderr.readline()
                if not line and proc.poll() is not None:
                    break
                
                if line:
                    line = line.strip()
                    if "bytes" in line and "copied" in line:
                        if last_was_progress:
                            self.root.after(0, self.log_overwrite_last_line, f">> {line}")
                        else:
                            self.root.after(0, self.log, f">> {line}")
                        last_was_progress = True
                    else:
                        self.root.after(0, self.log, line)
                        last_was_progress = False

            if proc.returncode == 0:
                self.root.after(0, self.log, "--- FLASH SUCCESS ---")
                messagebox.showinfo("Success", "Flashing Complete! Safe to remove.")
            else:
                self.root.after(0, self.log, "--- FLASH FAILED ---")
                messagebox.showerror("Error", "Flashing process returned an error.")
        
        except Exception as e:
            self.root.after(0, self.log, f"Error: {str(e)}")
        finally:
            self.root.after(0, lambda: self.btn_flash.config(state="normal"))

if __name__ == "__main__":
    root = tk.Tk()
    app = YoctoBuilderApp(root)
    root.mainloop()