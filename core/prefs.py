import json
from pathlib import Path

import config

_FILE = Path(__file__).parent.parent / "preferences.json"

DEFAULTS: dict = {
    "scan_interval_ms": 30,
    "click_cooldown": 0.3,
    "consecutive_frames": 1,
    "color_tolerance": 25,
    "use_opencv": True,
    "always_on_top": True,
    "debug": True,
    "max_clicks": 0,
    "post_click_pause": 0.0,
    "sound_on_click": False,
    "dark_mode": True,
}


def load() -> dict:
    """Return saved prefs merged over defaults (missing keys fall back to defaults)."""
    data = dict(DEFAULTS)
    if _FILE.exists():
        try:
            data.update(json.loads(_FILE.read_text(encoding="utf-8")))
        except Exception:
            pass
    return data


def save(p: dict) -> None:
    _FILE.write_text(json.dumps(p, indent=2), encoding="utf-8")


def apply(p: dict) -> None:
    """Write pref values into the live config module so they take effect immediately."""
    config.SCAN_INTERVAL = p["scan_interval_ms"] / 1000.0
    config.CLICK_COOLDOWN = float(p["click_cooldown"])
    config.CONSECUTIVE_FRAMES = int(p["consecutive_frames"])
    config.COLOR_TOLERANCE = int(p["color_tolerance"])
    config.USE_OPENCV = bool(p["use_opencv"])
    config.ALWAYS_ON_TOP = bool(p["always_on_top"])
    config.DEBUG = bool(p["debug"])
    config.MAX_CLICKS = int(p["max_clicks"])
    config.POST_CLICK_PAUSE = float(p["post_click_pause"])
    config.SOUND_ON_CLICK = bool(p["sound_on_click"])
    config.DARK_MODE = bool(p["dark_mode"])


def load_and_apply() -> dict:
    p = load()
    apply(p)
    return p
