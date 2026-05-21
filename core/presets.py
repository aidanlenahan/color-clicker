import json
from pathlib import Path

_FILE = Path(__file__).parent.parent / "presets.json"


def _read() -> dict:
    if not _FILE.exists():
        return {}
    try:
        return json.loads(_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write(data: dict) -> None:
    _FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def names() -> list[str]:
    return sorted(_read().keys())


def save(name: str, color: tuple, tolerance: int, region=None) -> None:
    data = _read()
    data[name] = {
        "color": list(color),
        "tolerance": tolerance,
        "region": list(region) if region else None,
    }
    _write(data)


def load(name: str) -> dict | None:
    """Returns {"color": (R,G,B), "tolerance": int, "region": (x,y,w,h)|None} or None."""
    entry = _read().get(name)
    if not entry:
        return None
    color = tuple(entry["color"])
    region = tuple(entry["region"]) if entry.get("region") else None
    return {"color": color, "tolerance": entry.get("tolerance", 25), "region": region}


def delete(name: str) -> None:
    data = _read()
    data.pop(name, None)
    _write(data)
