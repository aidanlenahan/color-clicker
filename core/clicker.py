import pyautogui

pyautogui.FAILSAFE = True   # move mouse to top-left corner to abort
pyautogui.PAUSE = 0         # no artificial delay between actions


class Clicker:
    def click(self, screen_x: int, screen_y: int) -> None:
        pyautogui.click(screen_x, screen_y)
