import ctypes


def enable_dpi_awareness():
    """Make this process DPI-aware so screen coords match actual pixels on scaled displays."""
    try:
        # Per-monitor V2 (Windows 10 1703+) — best option
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            # Fallback: system DPI aware
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
