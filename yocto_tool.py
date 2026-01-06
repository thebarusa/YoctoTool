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
        self.root.title("Yocto Manager & Flasher Tool (High Contrast)")
        self.root.geometry("900x750")

        # Variables
        self.poky_path = tk.StringVar()
        self.build_dir_name = tk.StringVar(value="build")
        self.machine_var = tk.StringVar(value="raspberrypi0-wifi")
        self.image_var = tk.StringVar(value="core-image-full-cmdline")
        self.selected_drive = tk.StringVar()
        
        # Check Root
        if os.geteuid() != 0:
            messagebox.showwarning("Permission Warning", "This tool must be run with 'sudo' to perform flashing operations!")

        self.create_widgets()

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
        ttk.Entry(frame_config, textvariable=self.machine_var, width=30).grid(row=0, column=1, padx=5, pady=5)

        # Image Selection (UPDATED: Combobox instead of Entry)
        ttk.Label(frame_config, text="IMAGE TARGET:").grid(row=0, column=2, padx=5, pady=5)
        
        # Common targets based on Yocto documentation
        common_targets = [
            "core-image-minimal",
            "core-image-base",
            "core-image-full-cmdline",
            "core-image-sato",
            "core-image-weston",
            "meta-toolchain",
            "meta-ide-support"
        ]
        
        self.image_combo = ttk.Combobox(frame_config, textvariable=self.image_var, values=common_targets, width=27)
        self.image_combo.grid(row=0, column=3, padx=5, pady=5)
        
        ttk.Button(frame_config, text="Save Config", command=self.save_config).grid(row=0, column=4, padx=5, pady=5)

        # --- Section 3: Build ---
        frame_build = ttk.LabelFrame(self.root, text="3. Build Process")
        frame_build.pack(fill="both", expand=True, padx=10, pady=5)

        btn_build = ttk.Button(frame_build, text="START BUILD (bitbake)", command=self.start_build_thread)
        btn_build.pack(pady=5)

        # UPDATED: High Contrast Terminal (White text on Black background, Monospace font)
        self.log_area = scrolledtext.ScrolledText(
            frame_build, 
            height=15, 
            state='disabled', 
            bg="#000000",       # Pure Black background
            fg="#FFFFFF",       # Pure White text
            insertbackground="white", # Cursor color
            font=("Courier New", 10, "bold") # Monospace font for better readability
        )
        self.log_area.pack(fill="both", expand=True, padx=5, pady=5)

        # --- Section 4: Flash ---
        frame_flash = ttk.LabelFrame(self.root, text="4. Flash to SD Card")
        frame_flash.pack(fill="x", padx=10, pady=10)

        ttk.Button(frame_flash, text="Refresh Drives", command=self.scan_drives).pack(side="left", padx=5)
        self.drive_menu = ttk.Combobox(frame_flash, textvariable=self.selected_drive, width=40, state="readonly")
        self.drive_menu.pack(side="left", padx=5)
        
        btn_flash = ttk.Button(frame_flash, text="FORMAT & FLASH", command=self.flash_image)
        btn_flash.pack(side="right", padx=20, pady=10)
        
        # Style adjustments
        style = ttk.Style()
        style.configure("TButton", font=('Helvetica', 10, 'bold'))

    def log(self, message):
        self.log_area.config(state='normal')
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)
        self.log_area.config(state='disabled')

    def browse_folder(self):
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.poky_path.set(folder_selected)

    def get_conf_path(self):
        return os.path.join(self.poky_path.get(), self.build_dir_name.get(), "conf", "local.conf")

    def load_config(self):
        conf_file = self.get_conf_path()
        if not os.path.exists(conf_file):
            messagebox.showerror("Error", f"Could not find local.conf at {conf_file}")
            return

        try:
            with open(conf_file, 'r') as f:
                content = f.read()
                
            # Regex to find MACHINE ??= "value" or MACHINE ?= "value"
            match_machine = re.search(r'^\s*MACHINE\s*\?{1,2}=\s*"(.*?)"', content, re.MULTILINE)
            if match_machine:
                self.machine_var.set(match_machine.group(1))
            
            self.log(f"Loaded configuration from {conf_file}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def save_config(self):
        conf_file = self.get_conf_path()
        if not os.path.exists(conf_file):
            return

        new_machine = self.machine_var.get()
        
        try:
            with open(conf_file, 'r') as f:
                lines = f.readlines()

            with open(conf_file, 'w') as f:
                machine_updated = False
                for line in lines:
                    if re.match(r'^\s*MACHINE\s*\?{1,2}=', line):
                        f.write(f'MACHINE ??= "{new_machine}"\n')
                        machine_updated = True
                    else:
                        f.write(line)
                
                if not machine_updated:
                    f.write(f'\nMACHINE ??= "{new_machine}"\n')
            
            self.log(f"Updated MACHINE to {new_machine} in local.conf")
            messagebox.showinfo("Success", "Configuration saved!")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def start_build_thread(self):
        if not self.poky_path.get():
            messagebox.showerror("Error", "Please select Poky root folder first.")
            return
        
        t = threading.Thread(target=self.run_build)
        t.start()

    def run_build(self):
        self.log("--- STARTING BUILD ---")
        poky_dir = self.poky_path.get()
        build_cmd = f"source oe-init-build-env {self.build_dir_name.get()} && bitbake {self.image_var.get()}"
        
        process = subprocess.Popen(
            f"cd {poky_dir} && {build_cmd}",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            executable="/bin/bash",
            universal_newlines=True
        )

        for line in process.stdout:
            self.log(line.strip())
        
        process.wait()
        
        if process.returncode == 0:
            self.log("--- BUILD SUCCESSFUL ---")
            messagebox.showinfo("Build", "Build Completed Successfully!")
        else:
            self.log("--- BUILD FAILED ---")
            messagebox.showerror("Build", "Build Failed. Check logs.")

    def scan_drives(self):
        try:
            cmd = "lsblk -d -o NAME,SIZE,MODEL,TRAN -n"
            output = subprocess.check_output(cmd, shell=True).decode()
            devices = []
            for line in output.split('\n'):
                if 'usb' in line or 'mmc' in line:
                    devices.append(line)
            
            if not devices:
                devices = ["No removable devices found"]
            
            self.drive_menu['values'] = devices
            if devices:
                self.drive_menu.current(0)
                
        except Exception as e:
            self.log(f"Error scanning drives: {e}")

    def flash_image(self):
        if os.geteuid() != 0:
            messagebox.showerror("Permission Error", "You must run this tool with 'sudo' to flash!")
            return

        selected = self.selected_drive.get()
        if not selected or "No removable" in selected:
            messagebox.showerror("Error", "Please select a valid drive.")
            return

        device_name = selected.split()[0]
        device_path = f"/dev/{device_name}"

        deploy_dir = os.path.join(self.poky_path.get(), self.build_dir_name.get(), "tmp/deploy/images", self.machine_var.get())
        
        search_pattern = os.path.join(deploy_dir, f"{self.image_var.get()}*.wic.bz2")
        files = glob.glob(search_pattern)
        
        if not files:
            search_pattern = os.path.join(deploy_dir, f"{self.image_var.get()}*.wic")
            files = glob.glob(search_pattern)

        if not files:
            messagebox.showerror("Error", f"No image found in {deploy_dir}")
            return

        latest_image = max(files, key=os.path.getctime)
        
        confirm = messagebox.askyesno("Confirm Flash", f"WARNING: This will ERASE ALL DATA on {device_path}.\n\nImage: {os.path.basename(latest_image)}\nTarget: {device_path}\n\nContinue?")
        
        if confirm:
            t = threading.Thread(target=self.run_flash, args=(latest_image, device_path))
            t.start()

    def run_flash(self, image_file, device_path):
        self.log(f"--- FLASHING {os.path.basename(image_file)} TO {device_path} ---")
        
        self.log("Unmounting drives...")
        subprocess.run(f"umount {device_path}*", shell=True)

        try:
            if image_file.endswith(".bz2"):
                cmd = f"bzcat {image_file} | dd of={device_path} bs=4M status=progress conv=fsync"
            else:
                cmd = f"dd if={image_file} of={device_path} bs=4M status=progress conv=fsync"

            proc = subprocess.Popen(cmd, shell=True, stderr=subprocess.PIPE)
            
            while True:
                line = proc.stderr.readline()
                if not line and proc.poll() is not None:
                    break
                if line:
                    pass 
            
            if proc.returncode == 0:
                self.log("--- FLASHING COMPLETE ---")
                messagebox.showinfo("Success", "Flashing Complete! You can remove the SD card.")
            else:
                self.log("--- FLASHING FAILED ---")
                messagebox.showerror("Error", "Flashing process returned an error.")

        except Exception as e:
            self.log(f"Flash error: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = YoctoBuilderApp(root)
    root.mainloop()