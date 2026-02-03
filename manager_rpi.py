import tkinter as tk
from tkinter import ttk
import os

class RpiManager:
    def __init__(self, root_app):
        self.root_app = root_app
        self.poky_path_var = root_app.poky_path
        self.root = root_app.root if hasattr(root_app, 'root') else root_app

        self.machines = ["raspberrypi0-wifi", "raspberrypi3", "raspberrypi4", "raspberrypi5"]

        # --- Variables ---
        self.rpi_hostname = tk.StringVar(value="raspberrypi-yocto")
        self.rpi_username = tk.StringVar(value="root")
        self.rpi_password = tk.StringVar(value="root")

        self.rpi_usb_gadget = tk.BooleanVar(value=False)
        self.rpi_enable_uart = tk.BooleanVar(value=True)
        self.license_commercial = tk.BooleanVar(value=True)
        self.rpi_enable_wifi = tk.BooleanVar(value=False)
        self.persistent_logs = tk.BooleanVar(value=True)
        self.wifi_ssid = tk.StringVar()
        self.wifi_password = tk.StringVar()

        self.frame_wifi_auth = None
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
            'BBLAYERS += "${TOPDIR}/../meta-openembedded/meta-networking"\n',
            'BBLAYERS += "${TOPDIR}/../meta-raspberrypi"\n'
        ]

    def create_tab(self, notebook):
        self.notebook = notebook
        self.tab = ttk.Frame(notebook)
        notebook.add(self.tab, text="Raspberry Pi Options")

        tab_rpi = self.tab
        
        tab_rpi.columnconfigure(0, weight=1)
        tab_rpi.columnconfigure(1, weight=1)

        # GROUP 1: SYSTEM & USER
        frame_sys = ttk.LabelFrame(tab_rpi, text=" 1. System Identity & User ")
        frame_sys.grid(row=0, column=0, padx=10, pady=5, sticky="nsew")

        ttk.Label(frame_sys, text="Hostname:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        ttk.Entry(frame_sys, textvariable=self.rpi_hostname, width=25).grid(row=0, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(frame_sys, text="Username:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        ttk.Entry(frame_sys, textvariable=self.rpi_username, width=25).grid(row=1, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(frame_sys, text="Password:").grid(row=2, column=0, padx=5, pady=5, sticky="e")
        ttk.Entry(frame_sys, textvariable=self.rpi_password, width=25).grid(row=2, column=1, padx=5, pady=5, sticky="w")

        lbl_note = ttk.Label(frame_sys, text="(User 'root' skips creation)", font=("Arial", 8, "italic"), foreground="gray")
        lbl_note.grid(row=3, column=1, sticky="w", padx=5, pady=(0, 5))

        # GROUP 2: HARDWARE
        frame_hw = ttk.LabelFrame(tab_rpi, text=" 2. Hardware & Drivers ")
        frame_hw.grid(row=0, column=1, padx=10, pady=5, sticky="nsew")

        ttk.Checkbutton(frame_hw, text="Enable UART Console (Serial)", variable=self.rpi_enable_uart).grid(row=0, column=0, sticky="w", padx=10, pady=2)
        ttk.Checkbutton(frame_hw, text="Enable USB Gadget Mode (SSH via USB)", variable=self.rpi_usb_gadget).grid(row=1, column=0, sticky="w", padx=10, pady=2)
        ttk.Checkbutton(frame_hw, text="Enable Persistent Logs (Save to SD)", variable=self.persistent_logs).grid(row=2, column=0, sticky="w", padx=10, pady=2)
        ttk.Separator(frame_hw, orient="horizontal").grid(row=3, column=0, sticky="ew", pady=5)
        ttk.Checkbutton(frame_hw, text="Accept Commercial Licenses (Codecs/Firmware)", variable=self.license_commercial).grid(row=4, column=0, sticky="w", padx=10, pady=2)

        # GROUP 3: CONNECTIVITY
        frame_net = ttk.LabelFrame(tab_rpi, text=" 3. Wireless Connectivity ")
        frame_net.grid(row=1, column=0, columnspan=2, padx=10, pady=10, sticky="ew")

        chk_wifi = ttk.Checkbutton(frame_net, text="Enable Wi-Fi Configuration", variable=self.rpi_enable_wifi, command=self.toggle_wifi_fields)
        chk_wifi.pack(anchor="w", padx=10, pady=5)

        self.frame_wifi_auth = ttk.Frame(frame_net)
        self.frame_wifi_auth.pack(fill="x", padx=20, pady=(0, 10))

        ttk.Label(self.frame_wifi_auth, text="SSID (Network Name):").pack(side="left")
        ttk.Entry(self.frame_wifi_auth, textvariable=self.wifi_ssid, width=25).pack(side="left", padx=5)
        
        ttk.Label(self.frame_wifi_auth, text="Password:").pack(side="left", padx=(15, 0))
        ttk.Entry(self.frame_wifi_auth, textvariable=self.wifi_password, width=25, show="*").pack(side="left", padx=5)

        self.toggle_wifi_fields()

    def toggle_wifi_fields(self):
        if self.frame_wifi_auth:
            if self.rpi_enable_wifi.get():
                self.frame_wifi_auth.pack(fill="x", padx=20, pady=(0, 10))
            else:
                self.frame_wifi_auth.pack_forget()

    def set_visible(self, visible):
        if not self.tab or not self.notebook:
            return
        try:
            state = self.notebook.tab(self.tab, "state")
            hidden = (state == "hidden")
            if visible and hidden:
                self.notebook.tab(self.tab, state="normal")
            elif not visible and not hidden:
                self.notebook.hide(self.tab)
        except:
            pass

    def get_state(self):
        return {
            "rpi_hostname": self.rpi_hostname.get(),
            "rpi_username": self.rpi_username.get(),
            "rpi_password": self.rpi_password.get(),
            "rpi_usb_gadget": self.rpi_usb_gadget.get(),
            "rpi_enable_uart": self.rpi_enable_uart.get(),
            "license_commercial": self.license_commercial.get(),
            "persistent_logs": self.persistent_logs.get(),
            "rpi_enable_wifi": self.rpi_enable_wifi.get(),
            "wifi_ssid": self.wifi_ssid.get(),
            "wifi_password": self.wifi_password.get()
        }

    def set_state(self, state):
        if not state:
            return
        self.rpi_hostname.set(state.get("rpi_hostname", "raspberrypi-yocto"))
        self.rpi_username.set(state.get("rpi_username", "root"))
        self.rpi_password.set(state.get("rpi_password", "root"))
        self.rpi_usb_gadget.set(state.get("rpi_usb_gadget", False))
        self.rpi_enable_uart.set(state.get("rpi_enable_uart", True))
        self.license_commercial.set(state.get("license_commercial", True))
        self.persistent_logs.set(state.get("persistent_logs", True))
        self.rpi_enable_wifi.set(state.get("rpi_enable_wifi", False))
        self.wifi_ssid.set(state.get("wifi_ssid", ""))
        self.wifi_password.set(state.get("wifi_password", ""))
        self.toggle_wifi_fields()

    def generate_wpa_config(self):
        poky_dir = self.poky_path_var.get()
        if not poky_dir or not os.path.exists(poky_dir):
            return

        layer_path = os.path.join(poky_dir, "meta-wifi-setup")
        recipe_dir = os.path.join(layer_path, "recipes-connectivity", "wpa-config")
        files_dir = os.path.join(recipe_dir, "files")

        os.makedirs(files_dir, exist_ok=True)
        os.makedirs(os.path.join(layer_path, "conf"), exist_ok=True)

        # 1. Layer Conf
        with open(os.path.join(layer_path, "conf", "layer.conf"), "w") as f:
            f.write('BBPATH .= ":${LAYERDIR}"\n')
            f.write('BBFILES += "${LAYERDIR}/recipes-*/*/*.bb"\n')
            f.write('BBFILES += "${LAYERDIR}/recipes-*/*/*.bbappend"\n') # FIX: Enable bbappend
            f.write('BBFILE_COLLECTIONS += "wifisetup"\n')
            f.write('BBFILE_PATTERN_wifisetup = "^${LAYERDIR}/"\n')
            f.write('BBFILE_PRIORITY_wifisetup = "10"\n')
            f.write('LAYERSERIES_COMPAT_wifisetup = "scarthgap"\n')

        # 2. WPA Supplicant Conf
        wpa_conf = f"""
ctrl_interface=/run/wpa_supplicant
update_config=1
country=VN

network={{
    ssid="{self.wifi_ssid.get()}"
    psk="{self.wifi_password.get()}"
}}
"""
        with open(os.path.join(files_dir, "wpa_supplicant.conf"), "w") as f:
            f.write(wpa_conf.strip() + "\n")

        # 3. Networkd Conf
        network_conf = """
[Match]
Name=wlan0

[Network]
DHCP=yes

[DHCPv4]
SendHostname=yes
"""
        with open(os.path.join(files_dir, "80-wifi.network"), "w") as f:
            f.write(network_conf.strip() + "\n")

        # 4. Service Conf
        wpa_service = """
[Unit]
Description=WPA Supplicant for wlan0
Before=network.target
After=dbus.service
Wants=network.target

[Service]
Type=simple
ExecStart=/usr/sbin/wpa_supplicant -i wlan0 -c /etc/wpa_supplicant/wpa_supplicant.conf
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
"""
        with open(os.path.join(files_dir, "wpa-wlan0.service"), "w") as f:
            f.write(wpa_service.strip() + "\n")

        # 5. Recipe WPA
        with open(os.path.join(recipe_dir, "wpa-config_1.0.bb"), "w") as f:
            f.write("""
SUMMARY = "WPA Supplicant and Networkd configuration"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = "file://wpa_supplicant.conf \\
           file://80-wifi.network \\
           file://wpa-wlan0.service"

S = "${WORKDIR}"

inherit systemd

SYSTEMD_SERVICE:${PN} = "wpa-wlan0.service"
SYSTEMD_AUTO_ENABLE:${PN} = "enable"

do_install() {
    install -d ${D}${sysconfdir}/wpa_supplicant
    install -m 600 ${WORKDIR}/wpa_supplicant.conf ${D}${sysconfdir}/wpa_supplicant/wpa_supplicant.conf

    install -d ${D}${sysconfdir}/systemd/network
    install -m 644 ${WORKDIR}/80-wifi.network ${D}${sysconfdir}/systemd/network/80-wifi.network

    install -d ${D}${systemd_system_unitdir}
    install -m 644 ${WORKDIR}/wpa-wlan0.service ${D}${systemd_system_unitdir}/wpa-wlan0.service
}

FILES:${PN} += "${sysconfdir}/wpa_supplicant/wpa_supplicant.conf \\
                ${sysconfdir}/systemd/network/80-wifi.network \\
                ${systemd_system_unitdir}/wpa-wlan0.service"
""")

        # 6. FIX: Create base-files bbappend to set hostname safely
        hostname = self.rpi_hostname.get().strip()
        if hostname:
            base_dir = os.path.join(layer_path, "recipes-core", "base-files")
            os.makedirs(base_dir, exist_ok=True)
            with open(os.path.join(base_dir, "base-files_%.bbappend"), "w") as f:
                f.write(f'hostname = "{hostname}"\n')

    def get_config_lines(self):
        lines = []
        
        # User Config
        user = self.rpi_username.get().strip()
        pwd = self.rpi_password.get().strip()
        
        if user and user != "root":
            lines.append('INHERIT += "extrausers"\n')
            pass_flag = f"-P '{pwd}'" if pwd else "-P 'root'" 
            lines.append(f'EXTRA_USERS_PARAMS += "useradd {pass_flag} -G sudo,video,render,input,shutdown,disk {user};"\n')

        lines.append(f'ENABLE_UART = "{"1" if self.rpi_enable_uart.get() else "0"}"\n')

        if self.license_commercial.get():
            lines.append('LICENSE_FLAGS_ACCEPTED:append = " commercial synaptics-killswitch"\n')

        if self.rpi_usb_gadget.get():
            lines.append('RPI_EXTRA_CONFIG:append = "dtoverlay=dwc2"\n')
            lines.append('KERNEL_MODULE_AUTOLOAD += "dwc2 g_ether"\n')
            lines.append('IMAGE_INSTALL:append = " kernel-module-dwc2 kernel-module-g-ether"\n')

        if self.persistent_logs.get():
            lines.append('VOLATILE_LOG_DIR = "no"\n')

        if self.rpi_enable_wifi.get():
            self.generate_wpa_config()
            lines.append('DISTRO_FEATURES:append = " systemd wifi usrmerge"\n')
            lines.append('VIRTUAL-RUNTIME_init_manager = "systemd"\n')
            lines.append('DISTRO_FEATURES_BACKFILL_CONSIDERED = "sysvinit"\n')
            lines.append('VIRTUAL-RUNTIME_initscripts = "systemd-compat-units"\n')
            
            lines.append('IMAGE_INSTALL:append = " wpa-supplicant iw linux-firmware-rpidistro-bcm43430 kernel-module-brcmfmac kernel-module-brcmfmac-wcc wpa-config wireless-regdb-static avahi-daemon libnss-mdns"\n')
            
            lines.append('KERNEL_MODULE_AUTOLOAD:append = " brcmfmac-wcc"\n')
            lines.append('CMDLINE:append = " brcmfmac.feature_disable=0x200000"\n')
            
        return lines