import tkinter as tk
from tkinter import ttk, messagebox
import os
import subprocess
import glob
import shlex

class UpdateManager:
    def __init__(self, root_app):
        self.root_app = root_app
        self.enable_rauc = tk.BooleanVar(value=False)
        self.rauc_slot_size = tk.StringVar(value="1024") # MB
        
        # SCP Variables
        self.target_ip = tk.StringVar(value="192.168.1.x")
        self.target_user = tk.StringVar(value="root")
        self.target_pass = tk.StringVar(value="root")

    def create_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="OTA Update (RAUC)")
        
        frame_cfg = ttk.LabelFrame(tab, text=" 1. Configuration ")
        frame_cfg.pack(fill="x", padx=10, pady=5)
        ttk.Checkbutton(frame_cfg, text="Enable RAUC (A/B Partitioning)", variable=self.enable_rauc).grid(row=0, column=0, sticky="w", padx=10, pady=5)
        ttk.Label(frame_cfg, text="Rootfs Size (MB):").grid(row=1, column=0, sticky="w", padx=10)
        ttk.Entry(frame_cfg, textvariable=self.rauc_slot_size, width=10).grid(row=1, column=1, sticky="w")
        ttk.Label(frame_cfg, text="(> Image Size)").grid(row=1, column=2, sticky="w", padx=5)

        frame_act = ttk.LabelFrame(tab, text=" 2. Build Actions ")
        frame_act.pack(fill="x", padx=10, pady=5)
        btn_keys = ttk.Button(frame_act, text="Generate Keys", command=self.generate_keys)
        btn_keys.grid(row=0, column=0, padx=10, pady=5, sticky="w")
        btn_bundle = ttk.Button(frame_act, text="BUILD UPDATE BUNDLE (.raucb)", command=self.build_bundle)
        btn_bundle.grid(row=0, column=1, padx=10, pady=5, sticky="w")
        ttk.Label(frame_act, text="(Build Image first, then Build Bundle)").grid(row=0, column=2, padx=10)

        frame_dep = ttk.LabelFrame(tab, text=" 3. Deployment (SCP Transfer) ")
        frame_dep.pack(fill="x", padx=10, pady=5)
        ttk.Label(frame_dep, text="Target IP:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        ttk.Entry(frame_dep, textvariable=self.target_ip, width=15).grid(row=0, column=1, padx=5, pady=5, sticky="w")
        ttk.Label(frame_dep, text="User:").grid(row=0, column=2, padx=5, pady=5, sticky="e")
        ttk.Entry(frame_dep, textvariable=self.target_user, width=10).grid(row=0, column=3, padx=5, pady=5, sticky="w")
        ttk.Label(frame_dep, text="Pass:").grid(row=0, column=4, padx=5, pady=5, sticky="e")
        ttk.Entry(frame_dep, textvariable=self.target_pass, width=10, show="*").grid(row=0, column=5, padx=5, pady=5, sticky="w")
        btn_send = ttk.Button(frame_dep, text="SEND BUNDLE TO PI", command=self.send_bundle_to_device)
        btn_send.grid(row=1, column=0, columnspan=6, pady=10, sticky="ew", padx=20)

    def build_bundle(self):
        if not self.enable_rauc.get():
            messagebox.showwarning("Warning", "Please enable RAUC first.")
            return
        self.root_app.start_specific_build("update-bundle")

    def send_bundle_to_device(self):
        if not self.check_sshpass(): return
        poky_dir = self.root_app.poky_path.get()
        build_dir = self.root_app.build_dir_name.get()
        machine = self.root_app.machine_var.get()
        deploy_dir = os.path.join(poky_dir, build_dir, "tmp/deploy/images", machine)
        if not os.path.exists(deploy_dir):
            messagebox.showerror("Error", "Deploy directory not found.")
            return
        files = glob.glob(os.path.join(deploy_dir, "*.raucb"))
        if not files:
            messagebox.showerror("Error", "No .raucb file found. Please build bundle first.")
            return
        bundle_file = max(files, key=os.path.getctime)
        file_name = os.path.basename(bundle_file)
        ip = self.target_ip.get()
        user = self.target_user.get()
        pwd = self.target_pass.get()
        target_path = f"/home/{user}/update.raucb" if user != "root" else "/home/root/update.raucb"
        self.root_app.log(f"Starting SCP transfer: {file_name} -> {ip}...")
        cmd = ["sshpass", "-p", pwd, "scp", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null", bundle_file, f"{user}@{ip}:{target_path}"]
        import threading
        threading.Thread(target=self.run_scp_thread, args=(cmd, file_name)).start()

    def run_scp_thread(self, cmd, filename):
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            self.root_app.log(f"SUCCESS: {filename} sent to device.")
            self.root_app.root.after(0, messagebox.showinfo, "Success", f"File sent successfully!\n\nNow run on Pi:\nrauc install update.raucb\nreboot")
        except subprocess.CalledProcessError as e:
            err_msg = e.stderr if e.stderr else str(e)
            self.root_app.log(f"SCP ERROR: {err_msg}")
            self.root_app.root.after(0, messagebox.showerror, "SCP Failed", f"Check IP/User/Pass.\nError: {err_msg}")

    def check_sshpass(self):
        from shutil import which
        if which("sshpass") is None:
            ans = messagebox.askyesno("Missing Component", "To auto-login, 'sshpass' is required.\nInstall it now? (sudo apt install sshpass)")
            if ans:
                try:
                    subprocess.run("sudo apt-get install -y sshpass", shell=True, check=True)
                    return True
                except:
                    messagebox.showerror("Error", "Failed to install sshpass.")
                    return False
            return False
        return True

    def generate_keys(self):
        project_root = os.getcwd()
        key_dir = os.path.join(project_root, "rauc-keys")
        if not os.path.exists(key_dir): os.makedirs(key_dir)
        cert_path = os.path.join(key_dir, "development-1.cert.pem")
        key_path = os.path.join(key_dir, "development-1.key.pem")
        if os.path.exists(cert_path) and os.path.exists(key_path):
            self.fix_key_permissions(key_dir)
            messagebox.showinfo("Info", f"Keys already exist. Permissions updated.")
            return
        cmd = f"""openssl req -new -newkey rsa:4096 -days 3650 -nodes -x509 -keyout {key_path} -out {cert_path} -subj "/C=VN/ST=HCM/L=Saigon/O=Yoctool/CN=rpi-update" """
        try:
            subprocess.run(cmd, shell=True, check=True)
            self.fix_key_permissions(key_dir)
            messagebox.showinfo("Success", f"Keys generated at:\n{key_dir}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def fix_key_permissions(self, key_dir):
        real_user = self.root_app.sudo_user
        if real_user and real_user != "root":
            try:
                subprocess.run(f"chown -R {real_user}:{real_user} {key_dir}", shell=True, check=True)
                self.root_app.log(f"Fixed permissions for {key_dir} to user {real_user}")
            except Exception as e:
                self.root_app.log(f"Warning fixing permissions: {e}")

    def create_wks_file(self):
        poky_dir = self.root_app.poky_path.get()
        if not poky_dir or not os.path.exists(poky_dir): return None
        layer_path = os.path.join(poky_dir, "meta-wifi-setup")
        wic_dir = os.path.join(layer_path, "wic")
        os.makedirs(wic_dir, exist_ok=True)
        wks_filename = "sdimage-dual-raspberrypi.wks"
        wks_path = os.path.join(wic_dir, wks_filename)
        size = self.rauc_slot_size.get()
        content = f"""
part /boot --source bootimg-partition --ondisk mmcblk0 --fstype=vfat --label boot --active --align 4096 --size 100
part / --source rootfs --ondisk mmcblk0 --fstype=ext4 --label rootfs_A --align 4096 --size {size}
part / --source rootfs --ondisk mmcblk0 --fstype=ext4 --label rootfs_B --align 4096 --size {size}
part /data --ondisk mmcblk0 --fstype=ext4 --label data --align 4096 --size 128
"""
        with open(wks_path, "w") as f: f.write(content)
        return wks_filename

    def create_rauc_config(self):
        poky_dir = self.root_app.poky_path.get()
        if not poky_dir: return
        layer_path = os.path.join(poky_dir, "meta-wifi-setup")
        rauc_recipe_dir = os.path.join(layer_path, "recipes-core", "rauc")
        rauc_files_dir = os.path.join(rauc_recipe_dir, "files")
        os.makedirs(rauc_files_dir, exist_ok=True)

        # 1. system.conf
        sys_conf_content = f"""
[system]
compatible={self.root_app.machine_var.get()}
bootloader=u-boot
[keyring]
path=development-1.cert.pem
[slot.rootfs.0]
device=/dev/mmcblk0p2
type=ext4
bootname=A
[slot.rootfs.1]
device=/dev/mmcblk0p3
type=ext4
bootname=B
"""
        with open(os.path.join(rauc_files_dir, "system.conf"), "w") as f: f.write(sys_conf_content.strip())
        
        # 2. fw_env.config
        fw_env_content = "/boot/uboot.env 0x0000 0x4000\n"
        with open(os.path.join(rauc_files_dir, "fw_env.config"), "w") as f: f.write(fw_env_content)

        # 3. bbappend (QUAN TRONG: Them lenh tao file uboot.env rong 16KB)
        bbappend_content = """
FILESEXTRAPATHS:prepend := "${THISDIR}/files:"
SRC_URI += "file://system.conf file://fw_env.config"

do_install:append() {
    install -d ${D}${sysconfdir}
    install -m 644 ${WORKDIR}/fw_env.config ${D}${sysconfdir}/fw_env.config
    
    # FIX: Tao file uboot.env rong 16KB de fw_printenv khong bi loi
    dd if=/dev/zero of=${D}/uboot.env bs=1024 count=16
}

FILES:${PN} += "/uboot.env"
"""
        with open(os.path.join(rauc_recipe_dir, "rauc-conf.bbappend"), "w") as f: f.write(bbappend_content.strip())

    def create_bundle_recipe(self):
        poky_dir = self.root_app.poky_path.get()
        if not poky_dir: return
        layer_path = os.path.join(poky_dir, "meta-wifi-setup")
        recipes_dir = os.path.join(layer_path, "recipes-core", "bundles")
        os.makedirs(recipes_dir, exist_ok=True)
        bundle_bb = os.path.join(recipes_dir, "update-bundle.bb")
        content = """
DESCRIPTION = "RAUC Update Bundle"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"
inherit bundle
RAUC_BUNDLE_COMPATIBLE = "${MACHINE}"
RAUC_BUNDLE_VERSION = "v1"
RAUC_BUNDLE_DESCRIPTION = "RAUC Bundle generated by Yoctool"
RAUC_BUNDLE_FORMAT = "verity" 
RAUC_BUNDLE_SLOTS = "rootfs" 
RAUC_SLOT_rootfs = "${RAUC_TARGET_IMAGE}"
RAUC_SLOT_rootfs[fstype] = "tar.gz"
RAUC_KEY_FILE = "${RAUC_KEY_FILE_REAL}"
RAUC_CERT_FILE = "${RAUC_CERT_FILE_REAL}"
"""
        with open(bundle_bb, "w") as f: f.write(content)

    def get_config_lines(self):
        if not self.enable_rauc.get(): return []
        wks_file = self.create_wks_file()
        self.create_rauc_config()
        self.create_bundle_recipe()
        
        project_root = os.getcwd()
        key_dir = os.path.join(project_root, "rauc-keys")
        cert_path = os.path.join(key_dir, "development-1.cert.pem")
        key_path = os.path.join(key_dir, "development-1.key.pem")

        lines = []
        lines.append('\n# --- RAUC OTA CONFIG ---\n')
        # FIX QUAN TRONG: Bat buoc RAUC phai compile voi u-boot support
        lines.append('DEPENDS:append:pn-rauc = " libubootenv"\n') 
        
        lines.append('RPI_USE_U_BOOT = "1"\n')
        lines.append('PREFERRED_PROVIDER_virtual/bootloader = "u-boot"\n')
        lines.append('DISTRO_FEATURES:append = " rauc"\n')
        lines.append('IMAGE_INSTALL:append = " rauc rauc-conf libubootenv-bin"\n') 
        
        if wks_file: lines.append(f'WKS_FILE = "{wks_file}"\n')
        lines.append(f'RAUC_KEY_FILE_REAL = "{key_path}"\n')
        lines.append(f'RAUC_CERT_FILE_REAL = "{cert_path}"\n')
        lines.append(f'RAUC_KEYRING_FILE = "{cert_path}"\n')
        current_image = self.root_app.image_var.get()
        lines.append(f'RAUC_TARGET_IMAGE = "{current_image}"\n')
        lines.append('IMAGE_FSTYPES:append = " wic.bz2"\n')
        lines.append('IMAGE_FSTYPES:append = " tar.gz"\n') 
        return lines

    def get_bblayers_lines(self):
        return ['BBLAYERS += "${TOPDIR}/../meta-rauc"\n']
    
    def get_required_layers(self):
        return [("meta-rauc", "https://github.com/rauc/meta-rauc")]