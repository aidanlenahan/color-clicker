import keyboard


class HotkeyManager:
    def __init__(self):
        self._keys: list[str] = []

    def register(self, key: str, callback) -> None:
        keyboard.add_hotkey(key, callback)
        self._keys.append(key)

    def clear(self) -> None:
        for key in self._keys:
            try:
                keyboard.remove_hotkey(key)
            except Exception:
                pass
        self._keys.clear()
