from utils.dpi import enable_dpi_awareness

# Must be called before any window or capture operation so that
# screen coordinates align with actual pixels on scaled displays (125%, 150% etc.)
enable_dpi_awareness()

from core import prefs
prefs.load_and_apply()   # apply saved preferences before creating any windows

from core.controller import Controller
from gui.app import App


def main() -> None:
    controller = Controller()
    app = App(controller)
    app.mainloop()


if __name__ == "__main__":
    main()
