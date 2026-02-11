import tkinter as tk
from tkinter import ttk, messagebox
import os
import subprocess
import glob
import threading

class OTATab:
    def __init__(self, root_app):
        self.root_app = root_app
        
        self.enable_rauc = tk.BooleanVar(value=False)
        self.rauc_slot_size = tk.StringVar(value="1024")
        
        self.target_ip = tk.StringVar(value="192.168.1.x")
        self.target_user = tk.StringVar(value="root")
        self.target_pass = tk.StringVar(value="root")

    def create_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="OTA Update (RAUC)")
        
        frame_cfg = ttk.LabelFrame(tab, text=" 1. RAUC Configuration ")
        frame_cfg.pack(fill="x", padx=10, pady=5)
        
        ttk.Checkbutton(frame_cfg, text="Enable RAUC (A/B Partitioning)", variable=self.enable_rauc).grid(row=0, column=0, sticky="w", padx=10, pady=5)
        
        ttk.Label(frame_cfg, text="Rootfs Slot Size (MB):").grid(row=1, column=0, sticky="w", padx=10)
        ttk.Entry(frame_cfg, textvariable=self.rauc_slot_size, width=10).grid(row=1, column=1, sticky="w")
        ttk.Label(frame_cfg, text="(Must be > Image Size)").grid(row=1, column=2, sticky="w", padx=5)

        frame_act = ttk.LabelFrame(tab, text=" 2. Build Actions ")
        frame_act.pack(fill="x", padx=10, pady=5)
        
        btn_keys = ttk.Button(frame_act, text="1. Generate Keys", command=self.generate_keys)
        btn_keys.grid(row=0, column=0, padx=10, pady=5, sticky="w")
        
        btn_bundle = ttk.Button(frame_act, text="2. BUILD UPDATE BUNDLE (.raucb)", command=self.build_bundle)
        btn_bundle.grid(row=0, column=1, padx=10, pady=5, sticky="w")
        
        ttk.Label(frame_act, text="(Note: Build standard Image first, then Build Bundle)").grid(row=0, column=2, padx=10)

        frame_dep = ttk.LabelFrame(tab, text=" 3. Deployment (SCP Transfer) ")
        frame_dep.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(frame_dep, text="Target IP:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        ttk.Entry(frame_dep, textvariable=self.target_ip, width=15).grid(row=0, column=1, padx=5, pady=5, sticky="w")
        
        ttk.Label(frame_dep, text="User:").grid(row=0, column=2, padx=5, pady=5, sticky="e")
        ttk.Entry(frame_dep, textvariable=self.target_user, width=10).grid(row=0, column=3, padx=5, pady=5, sticky="w")
        
        ttk.Label(frame_dep, text="Pass:").grid(row=0, column=4, padx=5, pady=5, sticky="e")
        ttk.Entry(frame_dep, textvariable=self.target_pass, width=10, show="*").grid(row=0, column=5, padx=5, pady=5, sticky="w")
        
        btn_send = ttk.Button(frame_dep, text="SEND BUNDLE & INSTALL", command=self.send_bundle_to_device)
        btn_send.grid(row=1, column=0, columnspan=6, pady=10, sticky="ew", padx=20)

    def build_bundle(self):
        if not self.enable_rauc.get():
            messagebox.showwarning("Warning", "Please enable RAUC first.")
            return
        if self.root_app.poky_path.get():
            self.root_app.start_specific_build("update-bundle")
        else:
            messagebox.showerror("Error", "Poky path not set")

    def send_bundle_to_device(self):
        if not self.check_sshpass(): return
        
        poky_dir = self.root_app.poky_path.get()
        build_dir = self.root_app.build_dir_name.get()
        machine = self.root_app.tab_general.machine_var.get()
        deploy_dir = os.path.join(poky_dir, build_dir, "tmp/deploy/images", machine)
        
        if not os.path.exists(deploy_dir):
            messagebox.showerror("Error", "Deploy directory not found. Build first.")
            return
            
        files = glob.glob(os.path.join(deploy_dir, "*.raucb"))
        if not files:
            messagebox.showerror("Error", "No .raucb file found. Please click 'BUILD UPDATE BUNDLE' first.")
            return
            
        bundle_file = max(files, key=os.path.getctime)
        file_name = os.path.basename(bundle_file)
        
        ip = self.target_ip.get()
        user = self.target_user.get()
        pwd = self.target_pass.get()
        target_path = f"/tmp/{file_name}"
        
        self.root_app.log(f"Starting SCP transfer: {file_name} -> {ip}...")
        
        cmd_scp = ["sshpass", "-p", pwd, "scp", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null", bundle_file, f"{user}@{ip}:{target_path}"]
        cmd_install = ["sshpass", "-p", pwd, "ssh", "-o", "StrictHostKeyChecking=no", f"{user}@{ip}", f"rauc install {target_path} && reboot"]
        
        threading.Thread(target=self.run_scp_thread, args=(cmd_scp, cmd_install, file_name)).start()

    def run_scp_thread(self, cmd_scp, cmd_install, filename):
        try:
            subprocess.run(cmd_scp, check=True, capture_output=True, text=True)
            self.root_app.log(f"SUCCESS: {filename} uploaded.")
            
            self.root_app.log("Installing update & Rebooting...")
            subprocess.run(cmd_install, capture_output=True, text=True)
            
            self.root_app.root.after(0, messagebox.showinfo, "Success", f"Update installed successfully!\nDevice is rebooting into the new partition.")
        except subprocess.CalledProcessError as e:
            err_msg = e.stderr if e.stderr else str(e)
            self.root_app.log(f"DEPLOY ERROR: {err_msg}")
            self.root_app.root.after(0, messagebox.showerror, "Deploy Failed", f"Check IP/User/Pass.\nError: {err_msg}")

    def check_sshpass(self):
        from shutil import which
        if which("sshpass") is None:
            if messagebox.askyesno("Missing Component", "Install 'sshpass' to deploy?"):
                subprocess.run("sudo apt-get install -y sshpass", shell=True)
                return True
            return False
        return True

    def generate_keys(self):
        project_root = os.getcwd()
        key_dir = os.path.join(project_root, "rauc-keys")
        if not os.path.exists(key_dir): os.makedirs(key_dir)
        
        cert_path = os.path.join(key_dir, "development-1.cert.pem")
        key_path = os.path.join(key_dir, "development-1.key.pem")
        
        if os.path.exists(cert_path) and os.path.exists(key_path):
            messagebox.showinfo("Info", f"Keys already exist in {key_dir}")
            return
            
        cmd = f"""openssl req -new -newkey rsa:4096 -days 3650 -nodes -x509 -keyout {key_path} -out {cert_path} -subj "/C=VN/ST=HCM/L=Saigon/O=Yoctool/CN=rpi-update" """
        try:
            subprocess.run(cmd, shell=True, check=True)
            real_user = self.root_app.sudo_user
            if real_user and real_user != "root":
                subprocess.run(f"chown -R {real_user}:{real_user} {key_dir}", shell=True)
            messagebox.showinfo("Success", f"Keys generated at:\n{key_dir}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

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

        machine = self.root_app.tab_general.machine_var.get()
        sys_conf_content = f"""
[system]
compatible={machine}
bootloader=uboot
data-directory=/var/lib/rauc

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
        
        fw_env_content = "/boot/uboot.env 0x0000 0x4000\n"
        with open(os.path.join(rauc_files_dir, "fw_env.config"), "w") as f: f.write(fw_env_content)

        for old_file in ["rauc-conf_1.0.bb", "rauc-conf_%.bbappend", "rauc-conf.bbappend"]:
            old_path = os.path.join(rauc_recipe_dir, old_file)
            if os.path.exists(old_path):
                try: os.remove(old_path)
                except: pass

        recipe_content = """
SUMMARY = "RPI Specific RAUC configuration"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = "file://system.conf file://fw_env.config"

PROVIDES += "rauc-conf virtual/rauc-conf"
RPROVIDES:${PN} += "rauc-conf virtual-rauc-conf"

RCONFLICTS:${PN} += "rauc-conf"
RREPLACES:${PN} += "rauc-conf"

S = "${WORKDIR}"

inherit deploy

do_compile() {
    dd if=/dev/zero of=${WORKDIR}/uboot.env bs=1024 count=16
}

do_install() {
    install -d ${D}${sysconfdir}/rauc
    install -m 644 ${WORKDIR}/system.conf ${D}${sysconfdir}/rauc/system.conf
    
    install -d ${D}${sysconfdir}
    install -m 644 ${WORKDIR}/fw_env.config ${D}${sysconfdir}/fw_env.config
}

do_deploy() {
    install -m 644 ${WORKDIR}/uboot.env ${DEPLOYDIR}/uboot.env
}

addtask deploy after do_compile before do_build

FILES:${PN} += "${sysconfdir}/rauc/system.conf ${sysconfdir}/fw_env.config"
"""
        with open(os.path.join(rauc_recipe_dir, "rpi-rauc-conf_1.0.bb"), "w") as f: f.write(recipe_content.strip())

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

        if not os.path.exists(key_path):
             self.root_app.log("Warning: RAUC Keys not found. Please click 'Generate Keys'.")

        lines = []
        lines.append('\n')
        
        lines.append('RPI_USE_U_BOOT = "1"\n')
        lines.append('PREFERRED_PROVIDER_virtual/bootloader = "u-boot"\n')
        lines.append('DEPENDS:append:pn-rauc = " libubootenv"\n')
        
        lines.append('PREFERRED_PROVIDER_rauc-conf = "rpi-rauc-conf"\n')
        lines.append('PREFERRED_PROVIDER_virtual/rauc-conf = "rpi-rauc-conf"\n')
        lines.append('BBMASK += "meta-rauc/recipes-core/rauc/rauc-conf.bb"\n')
        
        lines.append('PACKAGECONFIG:append:pn-rauc = " uboot"\n')
        
        lines.append('DISTRO_FEATURES:append = " rauc"\n')
        lines.append('IMAGE_INSTALL:append = " rauc rpi-rauc-conf libubootenv-bin"\n') 
        
        if wks_file: lines.append(f'WKS_FILE = "{wks_file}"\n')
        
        lines.append(f'RAUC_KEY_FILE_REAL = "{key_path}"\n')
        lines.append(f'RAUC_CERT_FILE_REAL = "{cert_path}"\n')
        lines.append(f'RAUC_KEYRING_FILE = "{cert_path}"\n')
        
        current_image = self.root_app.tab_general.image_var.get()
        lines.append(f'RAUC_TARGET_IMAGE = "{current_image}"\n')
        
        lines.append('IMAGE_BOOT_FILES:append = " uboot.env"\n')
        
        lines.append('IMAGE_FSTYPES:append = " wic.bz2"\n')
        lines.append('IMAGE_FSTYPES:append = " tar.gz"\n')
        
        lines.append('SYSTEMD_AUTO_ENABLE:pn-systemd-growfs = "disable"\n')
        lines.append('IMAGE_FEATURES:remove = "read-only-rootfs"\n')
        
        return lines

    def get_bblayers_lines(self):
        return ['BBLAYERS += "${TOPDIR}/../meta-rauc"\n']
    
    def get_required_layers(self):
        return [("meta-rauc", "https://github.com/rauc/meta-rauc -b scarthgap")]
    
    def get_state(self):
         return {
             "enable_rauc": self.enable_rauc.get(),
             "rauc_slot_size": self.rauc_slot_size.get(),
             "target_ip": self.target_ip.get(),
             "target_user": self.target_user.get()
         }
    
    def set_state(self, state):
        if not state: return
        self.enable_rauc.set(state.get("enable_rauc", False))
        self.rauc_slot_size.set(state.get("rauc_slot_size", "1024"))
        self.target_ip.set(state.get("target_ip", "192.168.1.x"))
        self.target_user.set(state.get("target_user", "root"))