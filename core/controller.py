import sys
import time
import threading

import config
from core.capture import ScreenCapture
from core.detector import ColorDetector
from core.clicker import Clicker
from utils import logger

_ERROR_LOG_INTERVAL = 10
_ERROR_BACKOFF_MAX = 1.0


class Controller:
    def __init__(self):
        self.region: tuple | None = None
        self.color: tuple | None = None

        self.running: bool = False
        self._thread: threading.Thread | None = None
        self._last_click: float = 0.0
        self._consec: int = 0
        self._click_count: int = 0

        self._capture = ScreenCapture()
        self._detector = ColorDetector()
        self._clicker = Clicker()

        self._click_cbs: list = []
        self._status_cbs: list = []
        self._highlight_cbs: list = []
        self._max_clicks_cbs: list = []

    # --- callback registration ---

    def on_click(self, fn) -> None:
        self._click_cbs.append(fn)

    def on_status(self, fn) -> None:
        self._status_cbs.append(fn)

    def on_highlight(self, fn) -> None:
        """Called with (region) when a match is found in dry-run mode."""
        self._highlight_cbs.append(fn)

    def on_max_clicks_reached(self, fn) -> None:
        self._max_clicks_cbs.append(fn)

    def _fire(self, cbs: list, *args) -> None:
        for fn in cbs:
            try:
                fn(*args)
            except Exception:
                pass

    def _fire_click(self, x: int, y: int) -> None:
        self._fire(self._click_cbs, x, y)

    def _fire_status(self, status: str) -> None:
        self._fire(self._status_cbs, status)

    def _fire_highlight(self, region: tuple) -> None:
        self._fire(self._highlight_cbs, region)

    def _fire_max_clicks(self) -> None:
        self._fire(self._max_clicks_cbs)

    # --- control ---

    def start(self) -> None:
        if self.running:
            return
        if not self.region or not self.color:
            logger.log("Cannot start: region or color not configured")
            return
        self.running = True
        self._click_count = 0
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        self._fire_status("running")
        logger.log("Started")

    def stop(self) -> None:
        self.running = False
        self._consec = 0
        self._fire_status("stopped")
        logger.log("Stopped")

    def toggle(self) -> None:
        if self.running:
            self.stop()
        else:
            self.start()

    # --- sound ---

    def _play_sound(self) -> None:
        if sys.platform == "win32":
            try:
                import winsound
                threading.Thread(
                    target=lambda: winsound.Beep(1000, 80), daemon=True
                ).start()
            except Exception:
                pass

    # --- scan loop ---

    def _loop(self) -> None:
        error_streak = 0

        while self.running:
            try:
                frame = self._capture.grab(self.region)
                match = self._detector.find_color(frame, self.color)

                if error_streak:
                    logger.log(f"Capture recovered after {error_streak} error(s)")
                    error_streak = 0

                if match:
                    self._consec += 1
                    if self._consec >= config.CONSECUTIVE_FRAMES:
                        now = time.time()
                        if now - self._last_click >= config.CLICK_COOLDOWN:
                            fx, fy = match
                            sx = self.region[0] + fx
                            sy = self.region[1] + fy

                            if config.DRY_RUN:
                                self._fire_highlight(self.region)
                                logger.log(f"[DRY] Match at ({sx}, {sy})")
                            else:
                                self._clicker.click(sx, sy)
                                if config.SOUND_ON_CLICK:
                                    self._play_sound()
                                if config.POST_CLICK_PAUSE > 0:
                                    time.sleep(config.POST_CLICK_PAUSE)
                                logger.log(f"Clicked ({sx}, {sy})")

                            self._last_click = now
                            self._click_count += 1
                            self._fire_click(sx, sy)

                            if config.MAX_CLICKS > 0 and self._click_count >= config.MAX_CLICKS:
                                logger.log(f"Max clicks ({config.MAX_CLICKS}) reached — auto-stopping")
                                self.running = False
                                self._consec = 0
                                self._fire_status("stopped")
                                self._fire_max_clicks()
                                return
                else:
                    self._consec = 0

                time.sleep(config.SCAN_INTERVAL)

            except Exception as exc:
                error_streak += 1
                if error_streak == 1 or error_streak % _ERROR_LOG_INTERVAL == 0:
                    logger.log(f"Capture error (×{error_streak}): {exc}")
                backoff = min(_ERROR_BACKOFF_MAX, config.SCAN_INTERVAL * (2 ** min(error_streak, 5)))
                time.sleep(backoff)
