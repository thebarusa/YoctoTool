import subprocess
import threading
import os
import shlex
import glob
from tkinter import filedialog, messagebox

class SDCardManager:
    def __init__(self, app):
        self.app = app

    def scan_drives(self):
        try:
            out = subprocess.check_output("lsblk -d -o NAME,SIZE,MODEL,TRAN -n", shell=True).decode()
            devs = [l for l in out.split('\n') if 'usb' in l or 'mmc' in l]
            self.app.drive_menu['values'] = devs if devs else ["No devices"]
            if devs: self.app.drive_menu.current(0)
        except: pass

    def format_drive(self):
        sel = self.app.selected_drive.get()
        if not sel or "No devices" in sel: return
        dev = f"/dev/{sel.split()[0]}"
        
        if messagebox.askyesno("Format Drive", f"DEEP WIPE & FORMAT {dev}?\nALL DATA WILL BE DESTROYED!"):
            self.app.set_busy_state(True)
            threading.Thread(target=self.run_format, args=(dev,)).start()

    def run_format(self, dev):
        try:
            self.app.root.after(0, lambda: self.app.pb_canvas.itemconfig(self.app.pb_rect, fill="#4CAF50"))
            self.app.log(f"Starting HARD WIPE on {dev}...")
            
            def run_step(desc, cmd):
                self.app.log(desc)
                p = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                if p.returncode != 0:
                    raise Exception(f"Command '{cmd}' failed.\nStderr: {p.stderr}")

            subprocess.run(f"umount -f {dev}*", shell=True, stderr=subprocess.DEVNULL)
            subprocess.run(f"swapoff {dev}*", shell=True, stderr=subprocess.DEVNULL)
            
            run_step("Nuking Partition Table...", f"dd if=/dev/zero of={shlex.quote(dev)} bs=512 count=2048 status=none conv=fsync")
            
            subprocess.run(f"wipefs -a --force {shlex.quote(dev)}", shell=True, stderr=subprocess.DEVNULL)
            
            subprocess.run("sync", shell=True)
            subprocess.run("udevadm settle", shell=True)
            subprocess.run(f"partprobe {shlex.quote(dev)}", shell=True)
            import time; time.sleep(2)
            
            run_step("Creating New Partition Table...", f"parted -s {shlex.quote(dev)} mklabel msdos")
            
            subprocess.run("udevadm settle", shell=True)
            time.sleep(1)
            
            run_step("Creating Partition...", f"parted -s {shlex.quote(dev)} mkpart primary fat32 0% 100%")
            
            subprocess.run("udevadm settle", shell=True)
            time.sleep(1)
            
            if dev[-1].isdigit(): part_dev = f"{dev}p1"
            else: part_dev = f"{dev}1"
            
            if not os.path.exists(part_dev):
                subprocess.run(f"partprobe {shlex.quote(dev)}", shell=True)
                time.sleep(1)

            run_step(f"Formatting {part_dev}...", f"mkfs.vfat -F 32 -n STORAGE {shlex.quote(part_dev)}")
            
            self.app.root.after(0, messagebox.showinfo, "Success", "Card Wiped & Restored")
            self.app.log("Hard Wipe Complete.")
            
        except Exception as e:
            self.app.root.after(0, lambda: self.app.pb_canvas.itemconfig(self.app.pb_rect, fill="#FF0000"))
            self.app.log(f"Format Error: {e}")
            self.app.root.after(0, lambda: messagebox.showerror("Error", f"Format failed:\n{str(e)}"))
        finally:
            self.app.root.after(0, self.app.set_busy_state, False)

    def flash_image(self):
        sel = self.app.selected_drive.get()
        if not sel or "No devices" in sel: return
        dev = f"/dev/{sel.split()[0]}"
        
        machine = self.app.tab_general.machine_var.get()
        image = self.app.tab_general.image_var.get()
        
        deploy = os.path.join(self.app.poky_path.get(), self.app.build_dir_name.get(), "tmp/deploy/images", machine)
        
        files = glob.glob(os.path.join(deploy, f"{image}*.sdimg"))
        if not files:
            files = glob.glob(os.path.join(deploy, f"{image}*.wic*"))
            
        if not files: 
            messagebox.showerror("Error", f"No image (.sdimg or .wic) found for {image}")
            return
            
        img = max(files, key=os.path.getctime)
        if messagebox.askyesno("Flash", f"Flash {os.path.basename(img)} to {dev}?"):
            self.app.set_busy_state(True)
            try: img_size = os.path.getsize(img)
            except: img_size = 0
            threading.Thread(target=self.run_flash, args=(img, dev, img_size)).start()

    def run_flash(self, img, dev, img_size):
        try:
            self.app.root.after(0, lambda: self.app.pb_canvas.itemconfig(self.app.pb_rect, fill="#4CAF50"))
            self.app.log("Preparing to flash...")
            
            subprocess.run(f"umount {shlex.quote(dev)}*", shell=True, stderr=subprocess.DEVNULL)
            
            self.app.log(f"Flashing {os.path.basename(img)}...")
            self.app.root.after(0, self.app.build_progress.set, 0)
            self.app.root.after(0, self.app.build_progress_text.set, "0%")
            
            safe_img = shlex.quote(img)
            safe_dev = shlex.quote(dev)
            
            if img.endswith(".bz2"): cmd = f"bzcat {safe_img} | dd of={safe_dev} bs=4M status=progress conv=fsync"
            else: cmd = f"dd if={safe_img} of={safe_dev} bs=4M status=progress conv=fsync"
            
            proc = subprocess.Popen(cmd, shell=True, stderr=subprocess.PIPE, universal_newlines=True)
            while True:
                line = proc.stderr.readline()
                if not line and proc.poll() is not None: break
                if "bytes" in line: 
                    self.app.log_overwrite(f">> {line.strip()}")
                    parts = line.split()
                    if parts and parts[0].isdigit() and img_size > 0:
                        bytes_copied = int(parts[0])
                        percent = (bytes_copied / img_size) * 100
                        percent = min(percent, 100)
                        self.app.root.after(0, self.app.build_progress.set, percent)
                        self.app.root.after(0, self.app.build_progress_text.set, f"{int(percent)}%")
            
            if proc.returncode == 0: 
                self.app.log("Refreshing partition table...")
                subprocess.run(f"partprobe {safe_dev}", shell=True)
                subprocess.run("udevadm settle", shell=True)

                self.app.root.after(0, self.app.build_progress.set, 100)
                self.app.root.after(0, self.app.build_progress_text.set, "100%")
                self.app.root.after(0, messagebox.showinfo, "Success", "Flashed! Partition table updated.")
        except Exception as e: 
            self.app.root.after(0, lambda: self.app.pb_canvas.itemconfig(self.app.pb_rect, fill="#FF0000"))
            self.app.root.after(0, messagebox.showerror, "Error", str(e))
        finally: 
             self.app.root.after(0, self.app.set_busy_state, False)

    def extract_logs(self):
        sel = self.app.selected_drive.get()
        if not sel or "No devices" in sel: return
        
        dev_name = sel.split()[0]
        dev_path = f"/dev/{dev_name}"
        
        if "mmcblk" in dev_name: part_path = f"{dev_path}p2"
        else: part_path = f"{dev_path}2"

        mount_point = "/tmp/yoctool_mnt"
        os.makedirs(mount_point, exist_ok=True)

        try:
            self.app.log(f"Mounting {part_path} to {mount_point}...")
            subprocess.run(f"mount {part_path} {mount_point}", shell=True, check=True)
            
            initial_dir = os.path.join(mount_point, "var/log/journal")
            if not os.path.exists(initial_dir): initial_dir = mount_point
            
            src_file = filedialog.askopenfilename(title="Select system.journal file", 
                                                initialdir=initial_dir,
                                                filetypes=[("Journal files", "*.journal"), ("All files", "*.*")])
            
            if src_file:
                real_user = os.environ.get('SUDO_USER') or os.environ.get('USER')
                home_dir = f"/home/{real_user}" if real_user and real_user != "root" else os.path.expanduser("~")
                
                dest_file = filedialog.asksaveasfilename(title="Save Log As",
                                                       initialdir=home_dir,
                                                       defaultextension=".txt",
                                                       filetypes=[("Text files", "*.txt")])
                if dest_file:
                    self.app.log(f"Converting {src_file} to {dest_file}...")
                    cmd = f"journalctl --file={shlex.quote(src_file)} --no-pager > {shlex.quote(dest_file)}"
                    subprocess.run(cmd, shell=True, check=True)
                    
                    if real_user and real_user != "root":
                        subprocess.run(f"chown {real_user}:{real_user} {shlex.quote(dest_file)}", shell=True)
                        
                    self.app.log("Log extracted successfully.")
                    messagebox.showinfo("Success", f"Log extracted to {dest_file}")

        except Exception as e:
            self.app.log(f"Error extracting logs: {e}")
            messagebox.showerror("Error", f"Failed: {e}")
        finally:
            subprocess.run(f"umount {mount_point}", shell=True)