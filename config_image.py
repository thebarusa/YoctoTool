import tkinter as tk
from tkinter import ttk

class ImageTab:
    def __init__(self, root_app):
        self.root_app = root_app
        
        # --- Variables ---
        self.feat_debug_tweaks = tk.BooleanVar(value=True)
        self.feat_ssh_server = tk.BooleanVar(value=True)
        self.feat_tools_debug = tk.BooleanVar(value=False)
        self.feat_package_mgmt = tk.BooleanVar(value=True)

    def create_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Image Features")
        
        frame_extra = ttk.LabelFrame(tab, text=" EXTRA_IMAGE_FEATURES ")
        frame_extra.pack(fill="x", padx=10, pady=10)

        ttk.Checkbutton(frame_extra, text="debug-tweaks (Allow root login without pass)", variable=self.feat_debug_tweaks).pack(anchor="w", padx=10, pady=2)
        ttk.Checkbutton(frame_extra, text="ssh-server-openssh (Install OpenSSH Server)", variable=self.feat_ssh_server).pack(anchor="w", padx=10, pady=2)
        ttk.Checkbutton(frame_extra, text="tools-debug (GDB, Strace, etc.)", variable=self.feat_tools_debug).pack(anchor="w", padx=10, pady=2)
        ttk.Checkbutton(frame_extra, text="package-management (Keep package manager in image)", variable=self.feat_package_mgmt).pack(anchor="w", padx=10, pady=2)

    def get_config_lines(self):
        features = []
        if self.feat_debug_tweaks.get(): features.append("debug-tweaks")
        if self.feat_ssh_server.get(): features.append("ssh-server-openssh")
        if self.feat_tools_debug.get(): features.append("tools-debug")
        if self.feat_package_mgmt.get(): features.append("package-management")
        
        if features:
            return [f'EXTRA_IMAGE_FEATURES ?= "{" ".join(features)}"\n']
        return []

    def get_state(self):
        return {
            "debug_tweaks": self.feat_debug_tweaks.get(),
            "ssh_server": self.feat_ssh_server.get(),
            "tools_debug": self.feat_tools_debug.get(),
            "package_mgmt": self.feat_package_mgmt.get()
        }

    def set_state(self, state):
        if not state: return
        self.feat_debug_tweaks.set(state.get("debug_tweaks", True))
        self.feat_ssh_server.set(state.get("ssh_server", True))
        self.feat_tools_debug.set(state.get("tools_debug", False))
        self.feat_package_mgmt.set(state.get("package_mgmt", True))