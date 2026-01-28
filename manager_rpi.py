import tkinter as tk
from tkinter import ttk
import os

class RpiManager:
    def __init__(self, root_app):
        self.root_app = root_app
        self.poky_path_var = root_app.poky_path 
        self.root = root_app.root if hasattr(root_app, 'root') else root_app
        
        self.machines = ["raspberrypi0-wifi", "raspberrypi3", "raspberrypi4", "raspberrypi5"]

        self.rpi_usb_gadget = tk.BooleanVar(value=False)
        self.rpi_enable_uart = tk.BooleanVar(value=True)
        self.license_commercial = tk.BooleanVar(value=True)
        self.rpi_enable_wifi = tk.BooleanVar(value=False)
        self.persistent_logs = tk.BooleanVar(value=True)
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
        
        ttk.Checkbutton(tab_rpi, text="Enable Persistent Logging (Save logs to SD Card)", variable=self.persistent_logs).grid(row=3, column=0, padx=10, pady=5, sticky="w")
        
        ttk.Checkbutton(tab_rpi, text="Enable Wi-Fi (Netplan + Systemd)", variable=self.rpi_enable_wifi, command=self.toggle_wifi_fields).grid(row=4, column=0, padx=10, pady=10, sticky="w")
        
        self.frame_wifi = ttk.Frame(tab_rpi)
        self.frame_wifi.grid(row=5, column=0, columnspan=2, padx=20, pady=0, sticky="w")
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

    def get_state(self):
        return {
            "rpi_usb_gadget": self.rpi_usb_gadget.get(),
            "rpi_enable_uart": self.rpi_enable_uart.get(),
            "license_commercial": self.license_commercial.get(),
            "persistent_logs": self.persistent_logs.get(),
            "rpi_enable_wifi": self.rpi_enable_wifi.get(),
            "wifi_ssid": self.wifi_ssid.get(),
            "wifi_password": self.wifi_password.get()
        }

    def set_state(self, state):
        if not state: return
        self.rpi_usb_gadget.set(state.get("rpi_usb_gadget", False))
        self.rpi_enable_uart.set(state.get("rpi_enable_uart", True))
        self.license_commercial.set(state.get("license_commercial", True))
        self.persistent_logs.set(state.get("persistent_logs", True))
        self.rpi_enable_wifi.set(state.get("rpi_enable_wifi", False))
        self.wifi_ssid.set(state.get("wifi_ssid", ""))
        self.wifi_password.set(state.get("wifi_password", ""))
        self.toggle_wifi_fields()

    def generate_wifi_layer_files(self):
        poky_dir = self.poky_path_var.get()
        if not poky_dir or not os.path.exists(poky_dir):
            return

        layer_path = os.path.join(poky_dir, "meta-wifi-setup")
        recipe_dir = os.path.join(layer_path, "recipes-core", "wifi-netplan-config")
        files_dir = os.path.join(recipe_dir, "files")
        
        os.makedirs(files_dir, exist_ok=True)
        os.makedirs(os.path.join(layer_path, "conf"), exist_ok=True)

        # 1. Create Layer Config
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

        # 2. Create Netplan Config
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

        # 3. Create Firmware Fix Script (The Magic Fix)
        # 168: Use 'grep -v "b0"' to avoid linking Pi Zero 2 W firmware (43430b0) on Pi Zero W (43430)
        script_content = """#!/bin/sh
# Aggressive Firmware Fixer for Pi Zero W (Debug Mode)
FW_DIR="/lib/firmware/brcm"
LOG="/tmp/wifi_fix.log"

log() {
    MSG="$(date): $1"
    echo "$MSG" >> $LOG
    echo "WIFI-FIX: $1" > /dev/kmsg 2>/dev/null || echo "WIFI-FIX: $1" # Try kernel log or stdout
}

log "Starting Wifi Fixer..."
log "Directory content before fix:"
ls -l $FW_DIR | while read line; do log "$line"; done

# Function to force link
link_firmware() {
    SRC=$1
    DST=$2
    if [ -f "$SRC" ]; then
        rm -rf "$DST" # Remove existing file/link
        ln -sf "$SRC" "$DST"
        log "Fixed: Linked $(basename $SRC) to $(basename $DST)"
    else
        log "Error: Source not found: $SRC"
    fi
}

# Helper to find best match
find_best_match() {
    PATTERN=$1
    EXCLUDE_SELF=$2
    
    # 1. Zero W Exact Match
    MATCH=$(find $FW_DIR -name "*model-zero-w*$PATTERN" ! -name "$EXCLUDE_SELF" | grep -v "b0" | head -n 1)
    
    # 2. 3 Model B (Compatible fallback)
    if [ -z "$MATCH" ]; then
        MATCH=$(find $FW_DIR -name "*3-model-b*$PATTERN" ! -name "$EXCLUDE_SELF" | grep -v "b0" | head -n 1)
    fi
    
    # 3. Generic (Catch-all, but NO b0)
    if [ -z "$MATCH" ]; then
        MATCH=$(find $FW_DIR -name "*43430*$PATTERN" ! -name "$EXCLUDE_SELF" | grep -v "b0" | head -n 1)
    fi
    
    # 4. Desperate fallback for txt file only (any purely named .txt)
    # Be careful not to pick the target itself if it exists
    if [ -z "$MATCH" ]; then
         MATCH=$(find $FW_DIR -name "*.txt" ! -name "$EXCLUDE_SELF" | grep "43430" | grep -v "b0" | head -n 1)
    fi

    echo "$MATCH"
}

# 1. Fix BIN file
BIN_SRC=$(find_best_match "sdio*.bin" "brcmfmac43430-sdio.bin")
if [ -n "$BIN_SRC" ]; then
    link_firmware "$BIN_SRC" "$FW_DIR/brcmfmac43430-sdio.bin"
else
    log "FAIL: No BIN source found for *sdio*.bin"
fi

# 2. Fix TXT file (Most critical for NVRAM)
TXT_SRC=$(find_best_match "sdio*.txt" "brcmfmac43430-sdio.txt")
if [ -n "$TXT_SRC" ]; then
    link_firmware "$TXT_SRC" "$FW_DIR/brcmfmac43430-sdio.txt"
else
    log "FAIL: No TXT source found for *sdio*.txt"
    # Debug: list all txt files
    find $FW_DIR -name "*.txt" | while read -r line; do log "Found txt: $line"; done
fi

# 3. Fix CLM_BLOB
CLM_SRC=$(find_best_match "sdio*.clm_blob" "brcmfmac43430-sdio.clm_blob")
if [ -n "$CLM_SRC" ]; then
    link_firmware "$CLM_SRC" "$FW_DIR/brcmfmac43430-sdio.clm_blob"
else
    log "FAIL: No CLM source found for *sdio*.clm_blob"
fi

# Reload driver to apply changes
modprobe -r brcmfmac
modprobe brcmfmac || log "Modprobe failed"
log "Finished."
"""
        with open(os.path.join(files_dir, "fix-wifi.sh"), "w") as f:
            f.write(script_content)

        # 4. Create Systemd Service for the script
        service_content = """[Unit]
Description=Fix Broadcom WiFi Firmware
Before=network-pre.target
Wants=network-pre.target

[Service]
Type=oneshot
ExecStart=/usr/bin/fix-wifi.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
"""
        with open(os.path.join(files_dir, "fix-wifi.service"), "w") as f:
            f.write(service_content)

        # 5. Create Bitbake Recipe
        recipe_content = """
SUMMARY = "Configure WiFi using Netplan and fix RPi Zero W firmware"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = "file://50-cloud-init.yaml \\
           file://fix-wifi.sh \\
           file://fix-wifi.service"

S = "${WORKDIR}"

inherit systemd

SYSTEMD_SERVICE:${PN} = "fix-wifi.service"
SYSTEMD_AUTO_ENABLE = "enable"

# Ensure firmware packages are present
RDEPENDS:${PN} += "linux-firmware-rpidistro-bcm43430 linux-firmware-bcm43430"

do_install() {
    # Install Netplan config
    install -d ${D}${sysconfdir}/netplan
    install -m 600 ${WORKDIR}/50-cloud-init.yaml ${D}${sysconfdir}/netplan/50-cloud-init.yaml

    # Install Fix Script
    install -d ${D}${bindir}
    install -m 0755 ${WORKDIR}/fix-wifi.sh ${D}${bindir}/fix-wifi.sh

    # Install Service
    install -d ${D}${systemd_unitdir}/system
    install -m 0644 ${WORKDIR}/fix-wifi.service ${D}${systemd_unitdir}/system/fix-wifi.service
}

FILES:${PN} += "${sysconfdir}/netplan/50-cloud-init.yaml \\
                ${bindir}/fix-wifi.sh \\
                ${systemd_unitdir}/system/fix-wifi.service"
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
            
        if self.persistent_logs.get():
            lines.append('VOLATILE_LOG_DIR = "no"\n')

        if self.rpi_enable_wifi.get():
            self.generate_wifi_layer_files()
            lines.append('DISTRO_FEATURES:append = " systemd usrmerge"\n')
            lines.append('VIRTUAL-RUNTIME_init_manager = "systemd"\n')
            lines.append('DISTRO_FEATURES_BACKFILL_CONSIDERED = "sysvinit"\n')
            lines.append('VIRTUAL-RUNTIME_initscripts = "systemd-compat-units"\n')
            lines.append('IMAGE_INSTALL:append = " netplan wifi-netplan-config"\n')
            lines.append('IMAGE_INSTALL:append = " kernel-module-brcmfmac"\n')
            # Install BOTH upstream and rpidistro firmware to ensure files exist
            lines.append('IMAGE_INSTALL:append = " linux-firmware-rpidistro-bcm43430"\n')
            lines.append('IMAGE_INSTALL:append = " linux-firmware-bcm43430"\n')
            lines.append('IMAGE_INSTALL:append = " wireless-regdb-static"\n')

        return lines