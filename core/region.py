import tkinter as tk
import mss


def _virtual_desktop() -> tuple[int, int, int, int]:
    """Return (left, top, width, height) of the combined virtual desktop across all monitors."""
    with mss.mss() as sct:
        vm = sct.monitors[0]   # index 0 is always the all-monitors bounding box
        return vm["left"], vm["top"], vm["width"], vm["height"]


class RegionSelector:
    @staticmethod
    def select_region(master: tk.Tk, callback) -> None:
        """
        Show a semi-transparent overlay spanning ALL monitors.
        User drags to define a rectangle, then releases to confirm.
        Calls callback((x, y, w, h)) on confirm, callback(None) on cancel/ESC.

        We avoid attributes("-fullscreen") because that only covers the primary
        monitor. Instead we manually size the window to the virtual desktop.
        """
        master.withdraw()

        vx, vy, vw, vh = _virtual_desktop()

        top = tk.Toplevel(master)
        top.attributes("-alpha", 0.25)
        top.attributes("-topmost", True)
        top.configure(bg="black")
        top.overrideredirect(True)
        # Position the window at the virtual desktop origin (can be negative
        # when a secondary monitor sits to the left or above the primary).
        top.geometry(f"{vw}x{vh}+{vx}+{vy}")
        top.focus_force()

        canvas = tk.Canvas(top, bg="black", cursor="cross", highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True)

        canvas.create_text(
            vw // 2, 44,
            text="Drag to select region     |     ESC to cancel",
            fill="white",
            font=("Segoe UI", 15, "bold"),
        )

        start: dict = {}
        rect_id: list = [None]
        result: list = [None]

        def on_press(e):
            start["x"] = e.x
            start["y"] = e.y
            if rect_id[0]:
                canvas.delete(rect_id[0])
                rect_id[0] = None

        def on_drag(e):
            if rect_id[0]:
                canvas.delete(rect_id[0])
            rect_id[0] = canvas.create_rectangle(
                start["x"], start["y"], e.x, e.y,
                outline="#ff3b3b", width=2,
            )

        def on_release(e):
            x1, y1 = start.get("x", 0), start.get("y", 0)
            x2, y2 = e.x, e.y
            w, h = abs(x2 - x1), abs(y2 - y1)
            if w > 5 and h > 5:
                # Canvas coords are relative to the window origin (vx, vy),
                # so add the virtual desktop offset to get true screen coords.
                result[0] = (vx + min(x1, x2), vy + min(y1, y2), w, h)
            done()

        def done():
            top.destroy()
            master.deiconify()
            callback(result[0])

        canvas.bind("<ButtonPress-1>", on_press)
        canvas.bind("<B1-Motion>", on_drag)
        canvas.bind("<ButtonRelease-1>", on_release)
        top.bind("<Escape>", lambda e: done())
