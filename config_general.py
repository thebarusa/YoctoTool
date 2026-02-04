import tkinter as tk
from tkinter import ttk
import multiprocessing
import os

class GeneralTab:
    def __init__(self, root_app):
        self.root_app = root_app
        
        # --- Variables ---
        self.machine_var = tk.StringVar(value="raspberrypi0-wifi")
        self.distro_var = tk.StringVar(value="poky")
        self.image_var = tk.StringVar(value="core-image-full-cmdline")
        
        self.pkg_format_var = tk.StringVar(value="package_rpm")
        self.init_system_var = tk.StringVar(value="systemd")
        
        cpu_count = multiprocessing.cpu_count()
        self.bb_threads_var = tk.IntVar(value=cpu_count)
        self.parallel_make_var = tk.IntVar(value=cpu_count)

    def create_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="General Settings")
        
        tab.columnconfigure(0, weight=1)
        tab.columnconfigure(1, weight=1)

        # Gather machines from other managers (e.g., RPi)
        all_machines = ["qemux86-64"]
        if hasattr(self.root_app, 'board_managers'):
            for mgr in self.root_app.board_managers:
                all_machines.extend(mgr.machines)

        grp_target = ttk.LabelFrame(tab, text=" Target Definition ")
        grp_target.grid(row=0, column=0, columnspan=2, padx=10, pady=5, sticky="ew")
        grp_target.columnconfigure(1, weight=1)
        grp_target.columnconfigure(3, weight=1)

        ttk.Label(grp_target, text="Machine:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.machine_combo = ttk.Combobox(grp_target, textvariable=self.machine_var, values=all_machines, width=25)
        self.machine_combo.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        self.machine_combo.bind("<<ComboboxSelected>>", self.root_app.update_ui_visibility)

        ttk.Label(grp_target, text="Distro:").grid(row=0, column=2, padx=5, pady=5, sticky="e")
        ttk.Combobox(grp_target, textvariable=self.distro_var, values=["poky", "poky-tiny", "poky-altcfg"], width=20).grid(row=0, column=3, padx=5, pady=5, sticky="w")

        ttk.Label(grp_target, text="Image Recipe:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.image_combo = ttk.Combobox(grp_target, textvariable=self.image_var, 
                                        values=["core-image-minimal", "core-image-base", "core-image-full-cmdline", "core-image-sato"], width=25)
        self.image_combo.grid(row=1, column=1, padx=5, pady=5, sticky="w")

        grp_sys = ttk.LabelFrame(tab, text=" System Core ")
        grp_sys.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")

        ttk.Label(grp_sys, text="Init Manager:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        ttk.OptionMenu(grp_sys, self.init_system_var, "systemd", "systemd", "sysvinit").grid(row=0, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(grp_sys, text="Package Format:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        ttk.OptionMenu(grp_sys, self.pkg_format_var, "package_rpm", "package_rpm", "package_deb", "package_ipk").grid(row=1, column=1, padx=5, pady=5, sticky="w")

        grp_perf = ttk.LabelFrame(tab, text=" Build Performance ")
        grp_perf.grid(row=1, column=1, padx=10, pady=5, sticky="nsew")

        ttk.Label(grp_perf, text="BB_NUMBER_THREADS:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        ttk.Spinbox(grp_perf, from_=1, to=64, textvariable=self.bb_threads_var, width=5).grid(row=0, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(grp_perf, text="PARALLEL_MAKE (-j):").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        ttk.Spinbox(grp_perf, from_=1, to=64, textvariable=self.parallel_make_var, width=5).grid(row=1, column=1, padx=5, pady=5, sticky="w")

    def get_config_lines(self):
        lines = []
        lines.append(f'MACHINE ??= "{self.machine_var.get()}"\n')
        lines.append(f'DISTRO ?= "{self.distro_var.get()}"\n')
        lines.append(f'PACKAGE_CLASSES ?= "{self.pkg_format_var.get()}"\n')
        lines.append(f'BB_NUMBER_THREADS = "{self.bb_threads_var.get()}"\n')
        lines.append(f'PARALLEL_MAKE = "-j {self.parallel_make_var.get()}"\n')
        
        # --- FIX: Dùng biến INIT_MANAGER thay vì chỉ set VIRTUAL-RUNTIME ---
        # Đây là chuẩn mới của Yocto, giúp các layer khác (như Mender) nhận diện đúng.
        if self.init_system_var.get() == "systemd":
            lines.append('INIT_MANAGER = "systemd"\n')
            # Các dòng dưới đây là bổ trợ (thường INIT_MANAGER tự xử lý, nhưng giữ lại cho chắc chắn)
            lines.append('DISTRO_FEATURES:append = " systemd usrmerge"\n')
            lines.append('VIRTUAL-RUNTIME_init_manager = "systemd"\n')
        elif self.init_system_var.get() == "sysvinit":
            lines.append('INIT_MANAGER = "sysvinit"\n')
            
        return lines

    def get_state(self):
        return {
            "machine": self.machine_var.get(),
            "distro": self.distro_var.get(),
            "image": self.image_var.get(),
            "pkg_format": self.pkg_format_var.get(),
            "init_system": self.init_system_var.get(),
            "bb_threads": self.bb_threads_var.get(),
            "parallel_make": self.parallel_make_var.get(),
        }

    def set_state(self, state):
        if not state: return
        self.machine_var.set(state.get("machine", "raspberrypi0-wifi"))
        self.distro_var.set(state.get("distro", "poky"))
        self.image_var.set(state.get("image", "core-image-full-cmdline"))
        self.pkg_format_var.set(state.get("pkg_format", "package_rpm"))
        self.init_system_var.set(state.get("init_system", "systemd"))
        self.bb_threads_var.set(state.get("bb_threads", multiprocessing.cpu_count()))
        self.parallel_make_var.set(state.get("parallel_make", multiprocessing.cpu_count()))