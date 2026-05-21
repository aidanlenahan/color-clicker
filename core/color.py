import tkinter as tk
from tkinter import simpledialog
import mss
import numpy as np


class ColorPicker:
    @staticmethod
    def pick_from_screen(master: tk.Tk, callback) -> None:
        """
        Floating preview window: user moves cursor to the target color and
        presses ENTER (or clicks Confirm) to lock it in.
        Calls callback((R, G, B)) on confirm, callback(None) on cancel.
        """
        sct = mss.mss()
        current_color: list = [None]

        top = tk.Toplevel(master)
        top.title("Pick Color from Screen")
        top.attributes("-topmost", True)
        top.geometry("230x130+10+10")
        top.resizable(False, False)

        tk.Label(top, text="Move cursor to target color", font=("Segoe UI", 9, "bold")).pack(pady=(10, 4))

        row = tk.Frame(top)
        row.pack(pady=2)

        swatch = tk.Label(row, width=5, height=2, bg="#cccccc", relief="solid")
        swatch.pack(side=tk.LEFT, padx=(10, 6))

        rgb_var = tk.StringVar(value="RGB(-, -, -)")
        tk.Label(row, textvariable=rgb_var, font=("Consolas", 9), width=14, anchor="w").pack(side=tk.LEFT)

        btn_row = tk.Frame(top)
        btn_row.pack(pady=8)

        def done(confirmed: bool):
            top.destroy()
            sct.close()
            callback(current_color[0] if confirmed else None)

        tk.Button(btn_row, text="Confirm  (Enter)", command=lambda: done(True),
                  font=("Segoe UI", 9), width=13).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_row, text="Cancel  (Esc)", command=lambda: done(False),
                  font=("Segoe UI", 9), width=13).pack(side=tk.LEFT, padx=4)

        top.bind("<Return>", lambda e: done(True))
        top.bind("<Escape>", lambda e: done(False))

        def update():
            if not top.winfo_exists():
                return
            try:
                px = top.winfo_pointerx()
                py = top.winfo_pointery()
                mon = {"left": px, "top": py, "width": 1, "height": 1}
                img = sct.grab(mon)
                pixel = np.array(img)[0, 0]
                b, g, r = int(pixel[0]), int(pixel[1]), int(pixel[2])
                hex_color = f"#{r:02x}{g:02x}{b:02x}"
                swatch.config(bg=hex_color)
                rgb_var.set(f"RGB({r}, {g}, {b})")
                current_color[0] = (r, g, b)
            except Exception:
                pass
            top.after(50, update)

        update()

    @staticmethod
    def pick_manual(master: tk.Tk, callback) -> None:
        """Prompt for a manual RGB value. Calls callback((R, G, B)) or callback(None)."""
        rgb_str = simpledialog.askstring(
            "Manual Color Input",
            "Enter RGB values separated by commas\ne.g.  255, 128, 0",
            parent=master,
        )
        if not rgb_str:
            callback(None)
            return
        try:
            parts = [int(x.strip()) for x in rgb_str.split(",")]
            if len(parts) == 3 and all(0 <= p <= 255 for p in parts):
                callback(tuple(parts))
                return
        except ValueError:
            pass
        callback(None)
