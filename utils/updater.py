import json
import threading
import urllib.request

import config

_API = f"https://api.github.com/repos/{config.REPO_URL.split('github.com/')[1]}/releases/latest"


def _parse_version(tag: str) -> tuple:
    return tuple(int(x) for x in tag.lstrip("v").split(".") if x.isdigit())


def check_for_update(callback) -> None:
    """Fire callback(latest_tag, release_url) in a daemon thread if a newer release exists."""
    def _run():
        try:
            req = urllib.request.Request(_API, headers={"User-Agent": "color-clicker"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
            tag = data.get("tag_name", "")
            url = data.get("html_url", "")
            if tag and _parse_version(tag) > _parse_version(config.VERSION):
                callback(tag, url)
        except Exception:
            pass

    threading.Thread(target=_run, daemon=True).start()
