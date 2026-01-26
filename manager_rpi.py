import tkinter as tk
from tkinter import ttk
import re
import os

class RpiManager:
    def __init__(self, root_app):
        self.root_app = root_app
        # Lay path cua poky tu app chinh de tao layer
        self.poky_path_var = root_app.poky_path 
        self.root = root_app.root if hasattr(root_app, 'root') else root_app
        
        self.machines = ["raspberrypi0-wifi", "raspberrypi3", "raspberrypi4", "raspberrypi5"]

        self.rpi_usb_gadget = tk.BooleanVar(value=False)
        self.rpi_enable_uart = tk.BooleanVar(value=True)
        self.license_commercial = tk.BooleanVar(value=True)
        self.rpi_enable_wifi = tk.BooleanVar(value=False)
        self.wifi_ssid = tk.StringVar()
        self.wifi_password = tk.StringVar()
        
        self.frame_wifi = None
        self.tab = None
        self.notebook = None

    def is_current_machine_supported(self):
        return self.root_app.machine_var.get() in self.machines

    def get_required_layers(self):
        return [
            ("meta-openembedded", "https://git.openembedded.org/meta-openembedded"),
            ("meta-raspberrypi", "https://git.yoctoproject.org/meta-raspberrypi")
        ]

    def get_bblayers_lines(self):
        # Them layer custom cua chung ta vao bblayers.conf
        return [
            'BBLAYERS += "${TOPDIR}/../meta-openembedded/meta-oe"\n',
            'BBLAYERS += "${TOPDIR}/../meta-openembedded/meta-python"\n',
            'BBLAYERS += "${TOPDIR}/../meta-openembedded/meta-networking"\n',
            'BBLAYERS += "${TOPDIR}/../meta-openembedded/meta-multimedia"\n',
            'BBLAYERS += "${TOPDIR}/../meta-raspberrypi"\n',
            'BBLAYERS += "${TOPDIR}/../meta-wifi-setup"\n'
        ]

    def create_tab(self, notebook):
        self.notebook = notebook
        self.tab = ttk.Frame(notebook)
        notebook.add(self.tab, text="Raspberry Pi Options")
        
        tab_rpi = self.tab
        
        ttk.Checkbutton(tab_rpi, text="Enable USB Gadget Mode (SSH over USB)", variable=self.rpi_usb_gadget).grid(row=0, column=0, padx=10, pady=5, sticky="w")
        ttk.Label(tab_rpi, text="(Adds 'dtoverlay=dwc2' & 'modules-load=dwc2,g_ether')").grid(row=0, column=1, sticky="w")
        
        ttk.Checkbutton(tab_rpi, text="Enable UART Console", variable=self.rpi_enable_uart).grid(row=1, column=0, padx=10, pady=5, sticky="w")
        ttk.Checkbutton(tab_rpi, text="Accept Commercial Licenses", variable=self.license_commercial).grid(row=2, column=0, padx=10, pady=5, sticky="w")
        
        ttk.Checkbutton(tab_rpi, text="Enable Wi-Fi (Netplan + Systemd)", variable=self.rpi_enable_wifi, command=self.toggle_wifi_fields).grid(row=3, column=0, padx=10, pady=10, sticky="w")
        
        self.frame_wifi = ttk.Frame(tab_rpi)
        self.frame_wifi.grid(row=4, column=0, columnspan=2, padx=20, pady=0, sticky="w")
        ttk.Label(self.frame_wifi, text="SSID:").pack(side="left")
        ttk.Entry(self.frame_wifi, textvariable=self.wifi_ssid, width=20).pack(side="left", padx=5)
        ttk.Label(self.frame_wifi, text="Password:").pack(side="left", padx=5)
        ttk.Entry(self.frame_wifi, textvariable=self.wifi_password, width=20, show="*").pack(side="left", padx=5)
        
        self.toggle_wifi_fields()

    def toggle_wifi_fields(self):
        if self.frame_wifi:
            if self.rpi_enable_wifi.get(): self.frame_wifi.grid()
            else: self.frame_wifi.grid_remove()

    def set_visible(self, visible):
        if not self.tab or not self.notebook: return
        try:
             current_state = self.notebook.tab(self.tab, "state")
             is_hidden = (current_state == "hidden")
             if visible and is_hidden:
                self.notebook.tab(self.tab, state="normal")
             elif not visible and not is_hidden:
                self.notebook.hide(self.tab)
        except: pass

    def parse_config(self, content):
        self.rpi_usb_gadget.set("dtoverlay=dwc2" in content)
        self.rpi_enable_uart.set('ENABLE_UART = "1"' in content)
        self.license_commercial.set("commercial" in content)
        
        if "wifi-netplan-config" in content:
            self.rpi_enable_wifi.set(True)
        else:
            self.rpi_enable_wifi.set(False)
        self.toggle_wifi_fields()

    def generate_wifi_layer_files(self):
        """
        Creates 'meta-wifi-setup' with a recipe for Netplan configuration.
        """
        poky_dir = self.poky_path_var.get()
        if not poky_dir or not os.path.exists(poky_dir):
            return

        layer_path = os.path.join(poky_dir, "meta-wifi-setup")
        recipe_dir = os.path.join(layer_path, "recipes-core", "wifi-netplan-config")
        files_dir = os.path.join(recipe_dir, "files")
        
        os.makedirs(files_dir, exist_ok=True)
        os.makedirs(os.path.join(layer_path, "conf"), exist_ok=True)

        # 1. Create layer.conf
        with open(os.path.join(layer_path, "conf", "layer.conf"), "w") as f:
            f.write('BBPATH .= ":${LAYERDIR}"\n')
            f.write('BBFILES += "${LAYERDIR}/recipes-*/*/*.bb \\\n')
            f.write('            ${LAYERDIR}/recipes-*/*/*.bbappend"\n')
            f.write('BBFILE_COLLECTIONS += "wifisetup"\n')
            f.write('BBFILE_PATTERN_wifisetup = "^${LAYERDIR}/"\n')
            f.write('BBFILE_PRIORITY_wifisetup = "10"\n')
            f.write('LAYERSERIES_COMPAT_wifisetup = "scarthgap kirkstone mickledore"\n')

        ssid = self.wifi_ssid.get()
        psk = self.wifi_password.get()

        # 2. Create Netplan YAML configuration
        # NOTE: Using 'networkd' renderer which works best with Systemd
        netplan_content = f"""network:
  version: 2
  renderer: networkd
  ethernets:
    eth0:
      dhcp4: true
      optional: true
  wifis:
    wlan0:
      dhcp4: true
      optional: true
      access-points:
        "{ssid}":
          password: "{psk}"
"""
        with open(os.path.join(files_dir, "50-cloud-init.yaml"), "w") as f:
            f.write(netplan_content)

        # 3. Create the BitBake recipe
        recipe_content = """
SUMMARY = "Configure WiFi using Netplan"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = "file://50-cloud-init.yaml"

S = "${WORKDIR}"

do_install() {
    # Install netplan config
    install -d ${D}${sysconfdir}/netplan
    install -m 600 ${WORKDIR}/50-cloud-init.yaml ${D}${sysconfdir}/netplan/50-cloud-init.yaml
}

FILES:${PN} += "${sysconfdir}/netplan/50-cloud-init.yaml"
"""
        with open(os.path.join(recipe_dir, "wifi-netplan-config_1.0.bb"), "w") as f:
            f.write(recipe_content)

    def get_config_lines(self):
        lines = []
        val = "1" if self.rpi_enable_uart.get() else "0"
        lines.append(f'ENABLE_UART = "{val}"\n')

        if self.license_commercial.get():
            lines.append('LICENSE_FLAGS_ACCEPTED:append = " commercial synaptics-killswitch"\n')

        if self.rpi_usb_gadget.get():
            lines.append('RPI_EXTRA_CONFIG:append = "dtoverlay=dwc2"\n')
            lines.append('KERNEL_MODULE_AUTOLOAD += "dwc2 g_ether"\n')
            lines.append('IMAGE_INSTALL:append = " kernel-module-dwc2 kernel-module-g-ether"\n')

        if self.rpi_enable_wifi.get():
            self.generate_wifi_layer_files()
            
            # FIX: ENABLE SYSTEMD & USRMERGE FOR NETPLAN
            # Netplan strictly depends on systemd, and systemd requires usrmerge
            lines.append('DISTRO_FEATURES:append = " systemd usrmerge"\n')
            lines.append('VIRTUAL-RUNTIME_init_manager = "systemd"\n')
            lines.append('DISTRO_FEATURES_BACKFILL_CONSIDERED = "sysvinit"\n')
            lines.append('VIRTUAL-RUNTIME_initscripts = "systemd-compat-units"\n')
            
            # Install packages
            lines.append('IMAGE_INSTALL:append = " netplan wifi-netplan-config linux-firmware-rpidistro-bcm43430"\n')

        return lines