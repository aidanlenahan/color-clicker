import config

_callbacks: list = []


def add_callback(fn) -> None:
    _callbacks.append(fn)


def log(msg: str) -> None:
    if config.DEBUG:
        print(f"[LOG] {msg}")
    for cb in _callbacks:
        try:
            cb(msg)
        except Exception:
            pass
