import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import os
import sys
import re
import subprocess
import multiprocessing

# --- UI Configs ---
import config_general
import config_image
import config_ota
import config_rpi

# --- Functional Managers ---
import manager_setup
import manager_build
import manager_sdcard

class YoctoolApp:
    def __init__(self, root):
        self.root = root
        
        self.APP_VERSION = self.get_version_from_filename()
        
        self.root.title(f"Yoctool {self.APP_VERSION} - Yocto Image Builder")
        self.root.geometry("950x900")

        # Global State Variables
        self.poky_path = tk.StringVar()
        self.build_dir_name = tk.StringVar(value="build")
        self.selected_drive = tk.StringVar()
        
        self.sudo_user = os.environ.get('SUDO_USER')
        if os.geteuid() != 0:
            messagebox.showwarning("Permission Warning", "Please run with 'sudo' to allow flashing.")
            if not self.sudo_user: self.sudo_user = os.environ.get('USER')
        if not self.sudo_user:
            self.sudo_user = "root"

        # Initialize Config Tabs
        self.tab_rpi = config_rpi.RpiTab(self)
        self.board_managers = [self.tab_rpi]
        self.active_manager = self.board_managers[0] 

        self.tab_general = config_general.GeneralTab(self)
        self.tab_image = config_image.ImageTab(self)
        self.tab_ota = config_ota.OTATab(self)
        
        self.build_progress = tk.DoubleVar()
        self.build_progress_text = tk.StringVar(value="0%")
        self.build_progress.trace_add("write", self._update_progress_canvas)
        
        self.config_file = os.path.expanduser("~/.yoctool_config")

        # Initialize Managers (Pass 'self' to allow access to UI/State)
        self.mgr_setup = manager_setup.SetupManager(self)
        self.mgr_build = manager_build.BuildManager(self)
        self.mgr_sdcard = manager_sdcard.SDCardManager(self)

        self.create_menu()
        self.create_widgets()
        
        # Initial Load
        self.mgr_setup.load_saved_path()
        self.log(f"Tool initialized. CPU Cores detected: {multiprocessing.cpu_count()}")

    def get_version_from_filename(self):
        version = "v1.0.0"
        if getattr(sys, 'frozen', False):
            exe_name = os.path.basename(sys.executable)
            match = re.search(r'Yoctool_(v\d+\.\d+\.\d+)', exe_name)
            if match:
                version = match.group(1)
        return version

    def create_menu(self):
        menubar = tk.Menu(self.root)
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label=f"Version: {self.APP_VERSION}", state="disabled")
        help_menu.add_separator()
        help_menu.add_command(label="Check for Update...", command=self.check_update)
        help_menu.add_command(label="About", command=self.show_about)
        menubar.add_cascade(label="Help", menu=help_menu)
        self.root.config(menu=menubar)

    def check_update(self):
        pass 

    def show_about(self):
        messagebox.showinfo("About", f"Yoctool\nVersion: {self.APP_VERSION}\nAuthor: Hungnt8687")

    def create_widgets(self):
        self._setup_path_section()
        self._setup_config_section()
        self._setup_operations_section()
        self._setup_log_section()

    def _setup_path_section(self):
        frame_setup = ttk.LabelFrame(self.root, text=" 1. Project Setup ")
        frame_setup.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(frame_setup, text="Poky Path:").grid(row=0, column=0, padx=5, pady=10, sticky="e")
        ttk.Entry(frame_setup, textvariable=self.poky_path, width=60).grid(row=0, column=1, padx=5, pady=10, sticky="ew")
        
        # Call Setup Manager
        ttk.Button(frame_setup, text="Browse", command=self.mgr_setup.browse_folder).grid(row=0, column=2, padx=5, pady=10)
        ttk.Button(frame_setup, text="Download Poky", command=self.mgr_setup.open_download_dialog).grid(row=0, column=3, padx=5, pady=10)
        frame_setup.columnconfigure(1, weight=1)

    def _setup_config_section(self):
        frame_config = ttk.LabelFrame(self.root, text=" 2. Configuration ")
        frame_config.pack(fill="x", padx=10, pady=5)
        
        notebook = ttk.Notebook(frame_config)
        notebook.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.tab_general.create_tab(notebook)
        self.tab_image.create_tab(notebook)
        self.tab_ota.create_tab(notebook)
        
        for mgr in self.board_managers:
            mgr.create_tab(notebook)
        
        frame_cfg_btns = ttk.Frame(frame_config)
        frame_cfg_btns.pack(pady=10)
        
        # Call Setup Manager for Load/Save
        self.btn_load = ttk.Button(frame_cfg_btns, text="LOAD CONFIG", command=self.mgr_setup.load_config)
        self.btn_load.pack(side="left", padx=10)
        self.btn_save = ttk.Button(frame_cfg_btns, text="APPLY & SAVE", command=self.mgr_setup.save_config)
        self.btn_save.pack(side="left", padx=10)
        
        self.update_ui_visibility()

    def update_ui_visibility(self, event=None):
        for mgr in self.board_managers:
            is_supported = mgr.is_current_machine_supported()
            mgr.set_visible(is_supported)
            if is_supported:
                self.active_manager = mgr

    def start_specific_build(self, target):
        # Wrapper to be called from OTATab
        self.mgr_build.start_specific_build(target)

    def _setup_operations_section(self):
        frame_ops = ttk.Frame(self.root)
        frame_ops.pack(fill="x", padx=10, pady=5)
        frame_top = ttk.Frame(frame_ops)
        frame_top.pack(side="top", fill="x", expand=True)

        frame_build = ttk.LabelFrame(frame_top, text=" 3. Build Operations ")
        frame_build.pack(side="left", fill="both", expand=True, padx=(0, 5))
        
        f_build_btns = ttk.Frame(frame_build)
        f_build_btns.pack(pady=15, padx=10)
        
        # Call Build Manager
        self.btn_build = ttk.Button(f_build_btns, text="START BUILD", command=self.mgr_build.start_build_thread)
        self.btn_build.pack(side="left", padx=10)
        self.btn_clean = ttk.Button(f_build_btns, text="CLEAN BUILD", command=self.mgr_build.start_clean_thread)
        self.btn_clean.pack(side="left", padx=10)

        frame_flash = ttk.LabelFrame(frame_top, text=" 4. SD Card & Logs ")
        frame_flash.pack(side="left", fill="both", expand=True, padx=(5, 0))
        
        f_flash_ctrl = ttk.Frame(frame_flash)
        f_flash_ctrl.pack(pady=15, padx=10, fill="x")
        self.drive_menu = ttk.Combobox(f_flash_ctrl, textvariable=self.selected_drive, width=15, state="readonly")
        self.drive_menu.pack(side="left", padx=5, fill="x", expand=True)
        
        # Call SDCard Manager
        ttk.Button(f_flash_ctrl, text="↻", width=3, command=self.mgr_sdcard.scan_drives).pack(side="left", padx=2)
        
        self.btn_format = ttk.Button(f_flash_ctrl, text="FORMAT", command=self.mgr_sdcard.format_drive)
        self.btn_format.pack(side="left", padx=5)
        
        self.btn_flash = ttk.Button(f_flash_ctrl, text="FLASH", command=self.mgr_sdcard.flash_image)
        self.btn_flash.pack(side="left", padx=5)
        
        self.btn_extract = ttk.Button(f_flash_ctrl, text="GET LOGS", command=self.mgr_sdcard.extract_logs)
        self.btn_extract.pack(side="left", padx=5)

        frame_progress = ttk.Frame(frame_ops)
        frame_progress.pack(side="top", fill="x", padx=0, pady=(5, 10))
        self.pb_canvas = tk.Canvas(frame_progress, height=25, bg="#e0e0e0", highlightthickness=1, highlightbackground="#999")
        self.pb_canvas.pack(fill="x", expand=True)
        self.pb_rect = self.pb_canvas.create_rectangle(0, 0, 0, 25, fill="#4CAF50", outline="")
        self.pb_text = self.pb_canvas.create_text(0, 12, text="0%", font=("Arial", 10, "bold"), fill="black")
        self.pb_canvas.bind("<Configure>", lambda e: self._update_progress_canvas())

    def _update_progress_canvas(self, *args):
        try:
            percent = self.build_progress.get()
            percent = max(0, min(100, percent))
            canvas_width = self.pb_canvas.winfo_width()
            if canvas_width <= 1: canvas_width = 400
            bar_width = (canvas_width * percent) / 100
            self.pb_canvas.coords(self.pb_rect, 0, 0, bar_width, 25)
            self.pb_canvas.itemconfig(self.pb_text, text=f"{int(percent)}%")
            self.pb_canvas.coords(self.pb_text, canvas_width / 2, 12)
        except: pass

    def _setup_log_section(self):
        frame_log = ttk.LabelFrame(self.root, text=" 5. Terminal Output ")
        frame_log.pack(fill="both", expand=True, padx=10, pady=5)
        self.log_area = scrolledtext.ScrolledText(frame_log, height=12, bg="black", fg="white", font=("Courier New", 10))
        self.log_area.pack(fill="both", expand=True, padx=5, pady=5)

    # --- Shared Utility Methods ---
    def log(self, msg):
        self.root.after(0, self._log_safe, msg)

    def _log_safe(self, msg):
        self.log_area.insert(tk.END, msg + "\n")
        self.log_area.see(tk.END)
    
    def log_overwrite(self, msg):
        self.root.after(0, self._log_overwrite_safe, msg)
    
    def _log_overwrite_safe(self, msg):
        self.log_area.delete("end-2l", "end-1l")
        self.log_area.insert(tk.END, msg + "\n")
        self.log_area.see(tk.END)

    def set_busy_state(self, busy):
        state = "disabled" if busy else "normal"
        self.btn_build.config(state=state)
        self.btn_clean.config(state=state)
        self.btn_format.config(state=state)
        self.btn_flash.config(state=state)
        self.btn_load.config(state=state)
        self.btn_save.config(state=state)
        self.btn_extract.config(state=state)

if __name__ == "__main__":
    if os.geteuid() != 0:
        try:
            subprocess.check_call(["sudo", sys.executable] + sys.argv)
        except subprocess.CalledProcessError:
            pass
        sys.exit(0)

    root = tk.Tk()
    app = YoctoolApp(root)
    root.mainloop()