import ctypes
import sys
import threading
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

import config
from core.controller import Controller
from core.region import RegionSelector
from core.color import ColorPicker
from core import presets
from core import prefs as core_prefs
from gui.highlight import RegionHighlight
from utils.hotkeys import HotkeyManager
from utils import logger

try:
    import pystray
    from PIL import Image as _PILImage, ImageDraw as _PILDraw
    _TRAY_OK = True
except ImportError:
    _TRAY_OK = False

THEMES = {
    "dark": {
        "bg":            "#1a1a1a",   # main window background
        "section_bg":    "#252526",   # LabelFrame interior (VS Code sidebar shade)
        "fg":            "#e8e8e8",   # main text — high contrast on dark
        "entry_bg":      "#3c3c3c",   # spinbox / input backgrounds
        "btn_bg":        "#3c3f41",
        "btn_fg":        "#d4d4d4",
        "btn_active_bg": "#4c5052",
        "dim_fg":        "#6e6e6e",   # secondary / hint text
        "log_bg":        "#111111",
        "log_fg":        "#a0a0a0",
        "check_select":  "#3c3c3c",
    },
    "light": {
        "bg":            "#f0f0f0",
        "section_bg":    "#e3e3e3",
        "fg":            "#1a1a1a",
        "entry_bg":      "#ffffff",
        "btn_bg":        "#dcdcdc",
        "btn_fg":        "#1a1a1a",
        "btn_active_bg": "#c8c8c8",
        "dim_fg":        "#888888",
        "log_bg":        "#ffffff",
        "log_fg":        "#444444",
        "check_select":  "#c0c0c0",
    },
}


class App(tk.Tk):
    def __init__(self, controller: Controller):
        super().__init__()
        self._controller = controller
        self._dark_mode: bool = config.DARK_MODE
        self._dim_labels: list = []
        self._tray = None
        self._highlight = RegionHighlight(self)
        self._click_count: int = 0

        self.title("Color Clicker")
        self.resizable(False, False)
        self.attributes("-topmost", config.ALWAYS_ON_TOP)

        self._seed_tk_options()   # populate option DB before any widget is created
        self._build_ui()
        self._apply_theme()
        self.update_idletasks()   # force Windows to render with the configured colors
        self._bind_controller()
        self._setup_hotkeys()
        self._setup_tray()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        # Dark title bar needs the HWND, which only exists after the event loop starts
        self.after(1, lambda: self._darken_titlebar(self))

    # ------------------------------------------------------------------ #
    #  Theme                                                               #
    # ------------------------------------------------------------------ #

    def _seed_tk_options(self) -> None:
        """Pre-populate the Tk option database so widgets inherit theme colors at construction."""
        t = self._get_theme()
        self.option_add("*background",       t["bg"])
        self.option_add("*foreground",       t["fg"])
        self.option_add("*selectBackground", t["entry_bg"])
        self.option_add("*selectForeground", t["fg"])
        self.option_add("*insertBackground", t["fg"])
        self.option_add("*activeBackground", t["btn_active_bg"])
        self.option_add("*activeForeground", t["btn_fg"])
        self.option_add("*Button.relief",    "flat")
        self.option_add("*Text.background",  t["log_bg"])
        self.option_add("*Text.foreground",  t["log_fg"])

    def _get_theme(self) -> dict:
        return THEMES["dark" if self._dark_mode else "light"]

    def _apply_theme(self, widget=None, _parent_bg=None) -> None:
        t = self._get_theme()
        if widget is None:
            widget = self

        # Never walk into the transparent overlay window
        if widget is getattr(self._highlight, "_win", None):
            return

        bg = _parent_bg if _parent_bg is not None else t["bg"]
        child_bg = bg  # children inherit current bg by default
        cls = widget.winfo_class()

        try:
            if cls in ("Frame", "Tk", "Toplevel"):
                widget.configure(bg=bg)
            elif cls == "LabelFrame":
                widget.configure(bg=t["section_bg"], fg=t["dim_fg"])
                child_bg = t["section_bg"]  # children sit on the section background
            elif cls == "Label":
                widget.configure(bg=bg, fg=t["fg"])
            elif cls == "Button":
                if widget not in (self._start_btn, self._stop_btn):
                    widget.configure(
                        bg=t["btn_bg"], fg=t["btn_fg"],
                        activebackground=t["btn_active_bg"],
                        activeforeground=t["btn_fg"],
                        relief="flat",
                    )
            elif cls == "Spinbox":
                widget.configure(
                    bg=t["entry_bg"], fg=t["fg"],
                    buttonbackground=t["btn_bg"],
                    insertbackground=t["fg"],
                    relief="flat",
                )
            elif cls == "Text":
                widget.configure(
                    bg=t["log_bg"], fg=t["log_fg"],
                    insertbackground=t["fg"],
                )
            elif cls == "Checkbutton":
                widget.configure(
                    bg=bg, fg=t["fg"],
                    selectcolor=t["check_select"],
                    activebackground=bg,
                    activeforeground=t["fg"],
                )
            elif cls == "Scrollbar":
                widget.configure(bg=t["btn_bg"], troughcolor=bg)
            elif cls == "TCombobox":
                pass  # handled via ttk styles
        except tk.TclError:
            pass

        for child in widget.winfo_children():
            self._apply_theme(child, _parent_bg=child_bg)

        # Post-walk fixups — only when re-theming the root window
        if widget is self:
            for lbl in self._dim_labels:
                try:
                    lbl.configure(fg=t["dim_fg"])
                except Exception:
                    pass
            self._restore_status_color()
            self._apply_ttk_theme(t)

    def _apply_ttk_theme(self, t: dict) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "TCombobox",
            fieldbackground=t["entry_bg"],
            background=t["btn_bg"],
            foreground=t["fg"],
            selectbackground=t["btn_bg"],
            selectforeground=t["fg"],
            arrowcolor=t["fg"],
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", t["entry_bg"])],
            selectbackground=[("readonly", t["btn_bg"])],
            foreground=[("readonly", t["fg"])],
        )

    def _restore_status_color(self) -> None:
        t = self._get_theme()
        if self._status_var.get() == "RUNNING":
            self._status_lbl.configure(fg="#27ae60")
        else:
            self._status_lbl.configure(fg=t["dim_fg"])

    def _darken_titlebar(self, window) -> None:
        """Apply dark or light title bar (caption bar) via the Windows DWM API."""
        if sys.platform != "win32":
            return
        try:
            window.update()
            hwnd = window.winfo_id()
            val = ctypes.c_int(1 if self._dark_mode else 0)
            # Attribute 20 = DWMWA_USE_IMMERSIVE_DARK_MODE (Windows 11 / 10 20H1+)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 20, ctypes.byref(val), ctypes.sizeof(val)
            )
        except Exception:
            try:
                # Attribute 19 = pre-20H1 Windows 10 fallback
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, 19, ctypes.byref(val), ctypes.sizeof(val)
                )
            except Exception:
                pass

    def _toggle_theme(self) -> None:
        self._dark_mode = not self._dark_mode
        config.DARK_MODE = self._dark_mode
        self._theme_btn.configure(text="☀" if self._dark_mode else "☾")
        self._seed_tk_options()   # update defaults for any future widgets (e.g., prefs dialog)
        self._apply_theme()
        self.update_idletasks()
        self._darken_titlebar(self)
        p = core_prefs.load()
        p["dark_mode"] = self._dark_mode
        core_prefs.save(p)

    # ------------------------------------------------------------------ #
    #  UI construction                                                     #
    # ------------------------------------------------------------------ #

    def _build_ui(self) -> None:
        t = self._get_theme()
        PAD = dict(padx=10, pady=5)

        # ---- status bar ----
        sf = tk.Frame(self, relief="flat", bd=0, bg=t["bg"])
        sf.pack(fill=tk.X, **PAD)
        tk.Label(sf, text="Status:", font=("Segoe UI", 10, "bold"),
                 bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT, padx=6, pady=4)
        self._status_var = tk.StringVar(value="IDLE")
        self._status_lbl = tk.Label(
            sf, textvariable=self._status_var,
            font=("Segoe UI", 10, "bold"), fg=t["dim_fg"], width=10, bg=t["bg"],
        )
        self._status_lbl.pack(side=tk.LEFT)
        self._counter_var = tk.StringVar(value="Clicks: 0")
        counter_lbl = tk.Label(sf, textvariable=self._counter_var,
                               font=("Segoe UI", 8), bg=t["bg"], fg=t["dim_fg"])
        counter_lbl.pack(side=tk.LEFT, padx=8)
        self._dim_labels.append(counter_lbl)
        self._theme_btn = tk.Button(
            sf, text="☀" if self._dark_mode else "☾",
            font=("Segoe UI", 10), command=self._toggle_theme,
            width=2, relief="flat", bd=0,
            bg=t["btn_bg"], fg=t["btn_fg"], activebackground=t["btn_active_bg"],
        )
        self._theme_btn.pack(side=tk.RIGHT, padx=2, pady=3)
        tk.Button(sf, text="Preferences", font=("Segoe UI", 8),
                  command=self._open_prefs, bg=t["btn_bg"], fg=t["btn_fg"],
                  activebackground=t["btn_active_bg"]).pack(side=tk.RIGHT, padx=6, pady=4)

        # ---- region ----
        rf = tk.LabelFrame(self, text="Region", font=("Segoe UI", 9),
                           bg=t["section_bg"], fg=t["dim_fg"])
        rf.pack(fill=tk.X, **PAD)
        self._region_var = tk.StringVar(value="Not set")
        tk.Label(rf, textvariable=self._region_var, font=("Segoe UI", 9), anchor="w",
                 width=24, bg=t["section_bg"], fg=t["fg"]).pack(side=tk.LEFT, padx=6, pady=4)
        tk.Button(rf, text="Select Region  (F8)", font=("Segoe UI", 9),
                  command=self._select_region, bg=t["btn_bg"], fg=t["btn_fg"],
                  activebackground=t["btn_active_bg"]).pack(side=tk.RIGHT, padx=6, pady=4)

        # ---- color ----
        cf = tk.LabelFrame(self, text="Target Color", font=("Segoe UI", 9),
                           bg=t["section_bg"], fg=t["dim_fg"])
        cf.pack(fill=tk.X, **PAD)
        self._swatch = tk.Label(cf, width=4, height=2, bg="#cccccc", relief="solid")
        self._swatch.pack(side=tk.LEFT, padx=(6, 4), pady=4)
        self._color_var = tk.StringVar(value="Not set")
        tk.Label(cf, textvariable=self._color_var, font=("Segoe UI", 9),
                 anchor="w", width=16, bg=t["section_bg"], fg=t["fg"]).pack(side=tk.LEFT, padx=4)
        btn_cf = tk.Frame(cf, bg=t["section_bg"])
        btn_cf.pack(side=tk.RIGHT, padx=6, pady=4)
        tk.Button(btn_cf, text="From Screen", font=("Segoe UI", 8),
                  command=self._pick_screen, bg=t["btn_bg"], fg=t["btn_fg"],
                  activebackground=t["btn_active_bg"]).pack(fill=tk.X, pady=1)
        tk.Button(btn_cf, text="Manual RGB", font=("Segoe UI", 8),
                  command=self._pick_manual, bg=t["btn_bg"], fg=t["btn_fg"],
                  activebackground=t["btn_active_bg"]).pack(fill=tk.X, pady=1)

        # ---- tolerance ----
        tf = tk.Frame(self, bg=t["bg"])
        tf.pack(fill=tk.X, padx=10, pady=2)
        tk.Label(tf, text="Tolerance ±", font=("Segoe UI", 9),
                 bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT)
        self._tol_var = tk.IntVar(value=config.COLOR_TOLERANCE)
        tk.Spinbox(tf, from_=1, to=120, textvariable=self._tol_var,
                   width=5, font=("Segoe UI", 9), relief="flat",
                   bg=t["entry_bg"], fg=t["fg"], buttonbackground=t["btn_bg"],
                   insertbackground=t["fg"]).pack(side=tk.LEFT, padx=5)
        dim = tk.Label(tf, text="per channel", font=("Segoe UI", 8),
                       bg=t["bg"], fg=t["dim_fg"])
        dim.pack(side=tk.LEFT)
        self._dim_labels.append(dim)
        self._tol_var.trace_add("write", self._on_tol_change)

        # ---- presets ----
        pf = tk.LabelFrame(self, text="Presets", font=("Segoe UI", 9),
                           bg=t["section_bg"], fg=t["dim_fg"])
        pf.pack(fill=tk.X, padx=10, pady=(4, 2))
        self._preset_swatch = tk.Label(pf, width=3, height=1, bg="#cccccc", relief="solid")
        self._preset_swatch.pack(side=tk.LEFT, padx=(6, 3), pady=5)
        self._preset_var = tk.StringVar()
        self._preset_combo = ttk.Combobox(
            pf, textvariable=self._preset_var, state="readonly",
            font=("Segoe UI", 9), width=20,
        )
        self._preset_combo.pack(side=tk.LEFT, padx=(0, 4), pady=5)
        self._preset_combo.bind("<<ComboboxSelected>>", lambda e: self._update_preset_swatch())
        self._refresh_presets()
        for _txt, _cmd in [("Load", self._load_preset), ("Save", self._save_preset),
                            ("Delete", self._delete_preset)]:
            tk.Button(pf, text=_txt, font=("Segoe UI", 8), width=6, command=_cmd,
                      bg=t["btn_bg"], fg=t["btn_fg"],
                      activebackground=t["btn_active_bg"]).pack(side=tk.LEFT, padx=2, pady=5)

        # ---- start / stop / dry-run ----
        ctrl = tk.Frame(self, bg=t["bg"])
        ctrl.pack(fill=tk.X, padx=10, pady=6)
        self._start_btn = tk.Button(
            ctrl, text="START  (F9)", width=14,
            bg="#27ae60", fg="white", activebackground="#2ecc71", activeforeground="white",
            font=("Segoe UI", 10, "bold"), relief="flat", command=self._start,
        )
        self._start_btn.pack(side=tk.LEFT, padx=(0, 6))
        self._stop_btn = tk.Button(
            ctrl, text="STOP  (F10)", width=14,
            bg="#c0392b", fg="white", activebackground="#e74c3c", activeforeground="white",
            font=("Segoe UI", 10, "bold"), relief="flat", command=self._stop,
            state=tk.DISABLED,
        )
        self._stop_btn.pack(side=tk.LEFT, padx=(0, 10))
        self._dry_var = tk.BooleanVar(value=config.DRY_RUN)
        tk.Checkbutton(
            ctrl, text="Dry Run", variable=self._dry_var,
            font=("Segoe UI", 9), command=self._on_dry_toggle,
            bg=t["bg"], fg=t["fg"], selectcolor=t["check_select"],
            activebackground=t["bg"], activeforeground=t["fg"],
        ).pack(side=tk.LEFT)

        # ---- hotkey hint ----
        hint = tk.Label(self, text="F8 Select Region  |  F9 Start  |  F10 Stop",
                        font=("Segoe UI", 7), bg=t["bg"], fg=t["dim_fg"])
        hint.pack(pady=(0, 4))
        self._dim_labels.append(hint)

        # ---- log ----
        lf = tk.LabelFrame(self, text="Log", font=("Segoe UI", 9),
                           bg=t["section_bg"], fg=t["dim_fg"])
        lf.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 8))
        self._log = tk.Text(lf, height=7, font=("Consolas", 8),
                            state=tk.DISABLED, wrap=tk.WORD, relief="flat",
                            bg=t["log_bg"], fg=t["log_fg"], insertbackground=t["fg"])
        sb = tk.Scrollbar(lf, command=self._log.yview,
                          bg=t["btn_bg"], troughcolor=t["section_bg"])
        self._log.config(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._log.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        logger.add_callback(self._append_log)

    # ------------------------------------------------------------------ #
    #  System tray                                                         #
    # ------------------------------------------------------------------ #

    def _make_tray_image(self):
        size = 64
        img = _PILImage.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = _PILDraw.Draw(img)
        cx = size // 2
        draw.ellipse([4, 4, size - 4, size - 4], fill="#27ae60")
        draw.rectangle([cx - 3, 14, cx + 3, size - 14], fill="white")
        draw.rectangle([14, cx - 3, size - 14, cx + 3], fill="white")
        return img

    def _setup_tray(self) -> None:
        if not _TRAY_OK:
            return
        menu = pystray.Menu(
            pystray.MenuItem("Show", self._tray_show, default=True),
            pystray.MenuItem(
                "Start / Stop",
                lambda icon, item: self.after(0, self._controller.toggle),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._tray_quit),
        )
        self._tray = pystray.Icon(
            "color-clicker", self._make_tray_image(), "Color Clicker", menu,
        )
        threading.Thread(target=self._tray.run, daemon=True).start()

    def _tray_show(self, *_) -> None:
        self.after(0, self._show_window)

    def _show_window(self) -> None:
        self.deiconify()
        self.lift()
        self.focus_force()

    def _tray_quit(self, *_) -> None:
        self.after(0, self._do_quit)

    def _do_quit(self) -> None:
        self._controller.stop()
        self._hotkeys.clear()
        self._highlight.destroy()
        if self._tray:
            try:
                self._tray.stop()
            except Exception:
                pass
        self.destroy()

    # ------------------------------------------------------------------ #
    #  Controller / hotkeys wiring                                         #
    # ------------------------------------------------------------------ #

    def _bind_controller(self) -> None:
        self._controller.on_click(
            lambda x, y: self.after(0, self._on_click, x, y)
        )
        self._controller.on_status(
            lambda s: self.after(0, self._set_status, s)
        )
        self._controller.on_highlight(
            lambda region: self.after(0, self._highlight.flash, region)
        )
        self._controller.on_max_clicks_reached(
            lambda: self.after(0, self._on_max_clicks_reached)
        )

    def _setup_hotkeys(self) -> None:
        self._hotkeys = HotkeyManager()
        self._hotkeys.register("F8", lambda: self.after(0, self._select_region))
        self._hotkeys.register("F9", lambda: self.after(0, self._start))
        self._hotkeys.register("F10", lambda: self.after(0, self._stop))

    # ------------------------------------------------------------------ #
    #  Actions                                                             #
    # ------------------------------------------------------------------ #

    def _select_region(self) -> None:
        RegionSelector.select_region(self, self._on_region_selected)

    def _on_region_selected(self, region) -> None:
        if region:
            self._controller.region = region
            x, y, w, h = region
            self._region_var.set(f"({x}, {y})   {w} × {h} px")
            self._append_log(f"Region: ({x}, {y}) {w}×{h}")
        else:
            self._append_log("Region selection cancelled")

    def _pick_screen(self) -> None:
        ColorPicker.pick_from_screen(self, self._on_color_picked)

    def _pick_manual(self) -> None:
        ColorPicker.pick_manual(self, self._on_color_picked)

    def _on_color_picked(self, color) -> None:
        if color:
            self._controller.color = color
            r, g, b = color
            self._swatch.config(bg=f"#{r:02x}{g:02x}{b:02x}")
            self._color_var.set(f"RGB({r}, {g}, {b})")
            self._append_log(f"Color: RGB({r}, {g}, {b})")
        else:
            self._append_log("Color pick cancelled")

    def _on_tol_change(self, *_) -> None:
        try:
            config.COLOR_TOLERANCE = self._tol_var.get()
        except Exception:
            pass

    def _on_dry_toggle(self) -> None:
        config.DRY_RUN = self._dry_var.get()
        self._append_log(f"Dry run {'ON — will highlight only, not click' if config.DRY_RUN else 'OFF'}")

    def _on_click(self, x: int, y: int) -> None:
        self._click_count += 1
        max_c = config.MAX_CLICKS
        suffix = f" / {max_c}" if max_c > 0 else ""
        self._counter_var.set(f"Clicks: {self._click_count}{suffix}")

    def _on_max_clicks_reached(self) -> None:
        self._append_log(f"Auto-stopped after {config.MAX_CLICKS} clicks")

    def _start(self) -> None:
        if not self._controller.region:
            messagebox.showwarning("No Region", "Select a screen region first (F8).", parent=self)
            return
        if not self._controller.color:
            messagebox.showwarning("No Color", "Pick a target color first.", parent=self)
            return
        self._click_count = 0
        max_c = config.MAX_CLICKS
        self._counter_var.set(f"Clicks: 0{' / ' + str(max_c) if max_c > 0 else ''}")
        self._controller.start()

    def _stop(self) -> None:
        self._controller.stop()

    def _set_status(self, status: str) -> None:
        t = self._get_theme()
        if status == "running":
            self._status_var.set("RUNNING")
            self._status_lbl.config(fg="#27ae60", bg=t["bg"])
            self._start_btn.config(state=tk.DISABLED)
            self._stop_btn.config(state=tk.NORMAL)
        else:
            self._status_var.set("IDLE")
            self._status_lbl.config(fg=t["dim_fg"], bg=t["bg"])
            self._start_btn.config(state=tk.NORMAL)
            self._stop_btn.config(state=tk.DISABLED)

    def _append_log(self, msg: str) -> None:
        self._log.config(state=tk.NORMAL)
        self._log.insert(tk.END, f"> {msg}\n")
        self._log.see(tk.END)
        self._log.config(state=tk.DISABLED)

    # ------------------------------------------------------------------ #
    #  Presets                                                             #
    # ------------------------------------------------------------------ #

    def _refresh_presets(self) -> None:
        names = presets.names()
        self._preset_combo["values"] = names
        if names and self._preset_var.get() not in names:
            self._preset_combo.set(names[0])
        elif not names:
            self._preset_var.set("")
        self._update_preset_swatch()

    def _update_preset_swatch(self) -> None:
        name = self._preset_var.get()
        data = presets.load(name) if name else None
        if data:
            r, g, b = data["color"]
            self._preset_swatch.config(bg=f"#{r:02x}{g:02x}{b:02x}")
        else:
            self._preset_swatch.config(bg="#cccccc")

    def _save_preset(self) -> None:
        if not self._controller.color:
            messagebox.showwarning("Nothing to save", "Pick a color before saving a preset.", parent=self)
            return
        name = simpledialog.askstring("Save Preset", "Preset name:", parent=self)
        if not name:
            return
        name = name.strip()
        if not name:
            return
        presets.save(name, self._controller.color, self._tol_var.get(), self._controller.region)
        self._refresh_presets()
        self._preset_combo.set(name)
        self._update_preset_swatch()
        self._append_log(f"Preset saved: {name}")

    def _load_preset(self) -> None:
        name = self._preset_var.get()
        if not name:
            messagebox.showwarning("No Preset", "Select a preset from the list first.", parent=self)
            return
        data = presets.load(name)
        if not data:
            messagebox.showerror("Missing", f"Preset '{name}' not found.", parent=self)
            self._refresh_presets()
            return
        self._on_color_picked(data["color"])
        self._tol_var.set(data["tolerance"])
        if data["region"]:
            self._on_region_selected(data["region"])
        self._append_log(f"Preset loaded: {name}")

    def _delete_preset(self) -> None:
        name = self._preset_var.get()
        if not name:
            return
        if not messagebox.askyesno("Delete Preset", f"Delete preset '{name}'?", parent=self):
            return
        presets.delete(name)
        self._append_log(f"Preset deleted: {name}")
        self._refresh_presets()

    # ------------------------------------------------------------------ #
    #  Preferences dialog                                                  #
    # ------------------------------------------------------------------ #

    def _open_prefs(self) -> None:
        p = core_prefs.load()

        top = tk.Toplevel(self)
        top.title("Preferences")
        top.resizable(False, False)
        top.attributes("-topmost", True)
        top.grab_set()
        top.focus_force()

        def spin_row(parent, row, label, var, lo, hi, suffix="", inc=1, fmt=None):
            tk.Label(parent, text=label, font=("Segoe UI", 9), anchor="w",
                     width=26).grid(row=row, column=0, padx=(10, 4), pady=4, sticky="w")
            kw = dict(from_=lo, to=hi, textvariable=var, width=7,
                      font=("Segoe UI", 9), increment=inc)
            if fmt:
                kw["format"] = fmt
            tk.Spinbox(parent, **kw).grid(row=row, column=1, padx=4, pady=4)
            tk.Label(parent, text=suffix, font=("Segoe UI", 8), fg="#666",
                     anchor="w").grid(row=row, column=2, padx=(2, 10), pady=4, sticky="w")

        def check_row(parent, row, label, var):
            tk.Checkbutton(parent, text=label, variable=var,
                           font=("Segoe UI", 9)).grid(
                row=row, column=0, columnspan=3, padx=10, pady=3, sticky="w")

        # ---- Detection ----
        det = tk.LabelFrame(top, text="Detection", font=("Segoe UI", 9))
        det.pack(fill=tk.X, padx=12, pady=(12, 4))
        scan_var = tk.IntVar(value=p["scan_interval_ms"])
        spin_row(det, 0, "Scan interval", scan_var, 5, 500, "ms  (~FPS = 1000 ÷ ms)", inc=5)
        frames_var = tk.IntVar(value=p["consecutive_frames"])
        spin_row(det, 1, "Consecutive frames", frames_var, 1, 20, "frames before clicking")
        opencv_var = tk.BooleanVar(value=p["use_opencv"])
        check_row(det, 2, "Use OpenCV detection (better blob center)", opencv_var)

        # ---- Clicking ----
        clk = tk.LabelFrame(top, text="Clicking", font=("Segoe UI", 9))
        clk.pack(fill=tk.X, padx=12, pady=4)
        cooldown_var = tk.DoubleVar(value=p["click_cooldown"])
        spin_row(clk, 0, "Click cooldown", cooldown_var, 0.05, 30.0,
                 "s between clicks", inc=0.05, fmt="%.2f")
        tol_var = tk.IntVar(value=p["color_tolerance"])
        spin_row(clk, 1, "Color tolerance", tol_var, 1, 120, "± per channel")
        max_clicks_var = tk.IntVar(value=p["max_clicks"])
        spin_row(clk, 2, "Max clicks", max_clicks_var, 0, 9999, "0 = unlimited")
        post_pause_var = tk.DoubleVar(value=p["post_click_pause"])
        spin_row(clk, 3, "Post-click pause", post_pause_var, 0.0, 30.0,
                 "s after each click", inc=0.1, fmt="%.1f")
        sound_var = tk.BooleanVar(value=p["sound_on_click"])
        check_row(clk, 4, "Sound on click  (short beep)", sound_var)

        # ---- Window ----
        win = tk.LabelFrame(top, text="Window", font=("Segoe UI", 9))
        win.pack(fill=tk.X, padx=12, pady=4)
        topmost_var = tk.BooleanVar(value=p["always_on_top"])
        check_row(win, 0, "Always on top", topmost_var)
        debug_var = tk.BooleanVar(value=p["debug"])
        check_row(win, 1, "Debug logging", debug_var)

        # ---- Buttons ----
        bf = tk.Frame(top)
        bf.pack(pady=10)

        def on_save():
            new_p = {
                "scan_interval_ms":  scan_var.get(),
                "click_cooldown":    round(cooldown_var.get(), 3),
                "consecutive_frames": frames_var.get(),
                "color_tolerance":   tol_var.get(),
                "use_opencv":        opencv_var.get(),
                "always_on_top":     topmost_var.get(),
                "debug":             debug_var.get(),
                "max_clicks":        max_clicks_var.get(),
                "post_click_pause":  round(post_pause_var.get(), 2),
                "sound_on_click":    sound_var.get(),
                "dark_mode":         self._dark_mode,
            }
            core_prefs.save(new_p)
            core_prefs.apply(new_p)
            self._tol_var.set(new_p["color_tolerance"])
            self.attributes("-topmost", new_p["always_on_top"])
            max_c = new_p["max_clicks"]
            self._counter_var.set(
                f"Clicks: {self._click_count}{' / ' + str(max_c) if max_c > 0 else ''}"
            )
            top.destroy()
            self._append_log("Preferences saved")

        tk.Button(bf, text="Save", width=10, font=("Segoe UI", 9),
                  command=on_save).pack(side=tk.LEFT, padx=6)
        tk.Button(bf, text="Cancel", width=10, font=("Segoe UI", 9),
                  command=top.destroy).pack(side=tk.LEFT, padx=6)

        # Apply theme and title bar after all widgets are built
        self._apply_theme(top)
        self._darken_titlebar(top)

        top.bind("<Return>", lambda e: on_save())
        top.bind("<Escape>", lambda e: top.destroy())

    # ------------------------------------------------------------------ #
    #  Close                                                               #
    # ------------------------------------------------------------------ #

    def _on_close(self) -> None:
        if _TRAY_OK and self._tray is not None:
            # Minimize to tray instead of quitting
            self.withdraw()
        else:
            self._do_quit()
