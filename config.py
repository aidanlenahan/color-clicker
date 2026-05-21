VERSION = "1.1"
REPO_URL = "https://github.com/aidanlenahan/color-clicker"

SCAN_INTERVAL = 0.03        # ~33 FPS scan rate
CLICK_COOLDOWN = 0.3        # seconds between clicks (anti-spam)
COLOR_TOLERANCE = 25        # per-channel RGB tolerance (0-255)
CONSECUTIVE_FRAMES = 1      # raise to 2-3 to filter flickering pixels
USE_OPENCV = True           # contour-based center vs simple centroid
ALWAYS_ON_TOP = True        # keep app window above other windows
DEBUG = True

MAX_CLICKS = 0              # auto-stop after this many clicks; 0 = unlimited
POST_CLICK_PAUSE = 0.0      # seconds to wait after each click before resuming scan
SOUND_ON_CLICK = False      # play a short beep on each click
DRY_RUN = False             # highlight only — do not move mouse or click
DARK_MODE = True            # UI theme; True = dark, False = light
