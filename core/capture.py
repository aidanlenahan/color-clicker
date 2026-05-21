import mss
import numpy as np


class ScreenCapture:
    def __init__(self):
        self._sct: mss.base.MSSBase | None = None
        self._open()

    def _open(self) -> None:
        if self._sct is not None:
            try:
                self._sct.close()
            except Exception:
                pass
        self._sct = mss.mss()

    def grab(self, region: tuple) -> np.ndarray:
        """Capture region (x, y, w, h). Returns BGR numpy array.
        Reinitializes the mss context on BitBlt / GDI failure so the caller
        can retry without tearing down the whole scan loop."""
        monitor = {
            "left": region[0],
            "top": region[1],
            "width": region[2],
            "height": region[3],
        }
        try:
            img = self._sct.grab(monitor)
            return np.array(img)[:, :, :3]  # BGRA -> BGR
        except Exception:
            self._open()   # stale GDI context — reinitialize then re-raise
            raise
