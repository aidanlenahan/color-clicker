import tkinter as tk

_TRANSPARENT = "black"
_OUTLINE = "#ff8800"
_BORDER_W = 4
_FLASH_MS = 200


class RegionHighlight:
    """Transparent borderless overlay that flashes an orange rectangle over a region.

    Uses -transparentcolor to punch a hole through the window so only the
    outline is visible; the interior stays click-through on Windows.
    """

    def __init__(self, root: tk.Tk) -> None:
        self._root = root
        self._win: tk.Toplevel | None = None
        self._canvas: tk.Canvas | None = None
        self._hide_job = None
        self._last_region: tuple | None = None

    def flash(self, region: tuple) -> None:
        x, y, w, h = region

        if self._win is None:
            self._win = tk.Toplevel(self._root)
            self._win.overrideredirect(True)
            self._win.attributes("-topmost", True)
            self._win.attributes("-transparentcolor", _TRANSPARENT)
            self._win.configure(bg=_TRANSPARENT)
            self._canvas = tk.Canvas(
                self._win, highlightthickness=0, bg=_TRANSPARENT
            )
            self._canvas.pack(fill=tk.BOTH, expand=True)

        if region != self._last_region:
            self._win.geometry(f"{w}x{h}+{x}+{y}")
            self._canvas.config(width=w, height=h)
            self._canvas.delete("all")
            b = _BORDER_W // 2
            self._canvas.create_rectangle(
                b, b, w - b, h - b,
                outline=_OUTLINE,
                width=_BORDER_W,
            )
            self._last_region = region

        self._win.deiconify()

        if self._hide_job:
            self._root.after_cancel(self._hide_job)
        self._hide_job = self._root.after(_FLASH_MS, self._hide)

    def _hide(self) -> None:
        if self._win:
            self._win.withdraw()

    def destroy(self) -> None:
        if self._win:
            self._win.destroy()
            self._win = None
            self._canvas = None
