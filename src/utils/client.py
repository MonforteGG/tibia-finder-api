"""
Tibia client automation — keyboard only.

Flow:
  1. Tibia.exe opens directly on the login screen with the email pre-filled
     and focus already on the password field.
  2. Type password + Enter → character list.
  3. Down × char_index + Enter → in-game.
  4. Enter → type exiva "Name" → Enter → spell cast.
  5. Logout: Ctrl+Q → returns to character selection.
"""

import ctypes
import os
import time
from random import uniform, gauss
import pyautogui
import pygetwindow as gw

from utils.human_movement import move_mouse_like_human

pyautogui.PAUSE = 0.1
pyautogui.FAILSAFE = True


def _jitter(base: float, pct: float = 0.25) -> float:
    """Returns base ± pct*base with Gaussian distribution, minimum 0.05s."""
    return max(0.05, gauss(base, base * pct))


def _typing_interval() -> float:
    """Inter-keystroke interval — varies like a real person."""
    return uniform(0.04, 0.14)


def _foreground_window_title() -> str:
    """Title of the window that currently has focus (native Win32)."""
    hwnd = ctypes.windll.user32.GetForegroundWindow()
    length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


class Client:
    LOGIN_WINDOW_TIMEOUT = 60
    INGAME_TIMEOUT = 40

    def __init__(
        self,
        executable: str,
        email: str,
        password: str,
        char_index: int,
        load_seconds: float = 10,
    ):
        self.executable = executable
        self.email = email
        self.password = password
        self.char_index = char_index
        self.load_seconds = load_seconds
        self._already_running = False

    # ------------------------------------------------------------------ #
    #  Lifecycle
    # ------------------------------------------------------------------ #

    def start(self):
        """Launch Tibia if not running. If a window already exists, focus and reuse it."""
        if self._get_window():
            self._already_running = True
            self._log("Client already open, reusing window.")
            self._focus()
            return

        if not os.path.exists(self.executable):
            raise FileNotFoundError(f"Executable not found: {self.executable}")

        self._already_running = False
        # os.startfile uses ShellExecute — guarantees a visible window with the
        # correct desktop context regardless of how the parent process was launched.
        os.startfile(self.executable)
        self._log(f"Launching {self.executable} — waiting for window (max {self.LOGIN_WINDOW_TIMEOUT}s)...")
        self._wait_for_window("Tibia", timeout=self.LOGIN_WINDOW_TIMEOUT)
        time.sleep(_jitter(self.load_seconds, pct=0.1))
        self._log("Login window ready.")

    def login(self):
        """Full login from the login screen: types password and selects character."""
        self._focus()
        time.sleep(_jitter(0.6))

        pyautogui.typewrite(self.password, interval=_typing_interval())
        time.sleep(_jitter(0.4))
        pyautogui.press("enter")
        self._log("Password sent, waiting for character list...")
        time.sleep(_jitter(6.5, pct=0.15))

        self._select_char()

    def select_character(self):
        """Move down one character and enter. Use after Ctrl+Q logout,
        when the cursor is already on the previous character."""
        self._focus()
        time.sleep(_jitter(0.6))
        pyautogui.press("down")
        time.sleep(_jitter(0.25))
        self._enter_char()

    def _select_char(self):
        """Navigate from the first character to char_index and press Enter.
        Use only on initial login, when the cursor starts at position 0."""
        for _ in range(self.char_index):
            pyautogui.press("down")
            time.sleep(_jitter(0.25))
        self._enter_char()

    def _enter_char(self):
        """Press Enter on the selected character and wait until in-game."""
        time.sleep(_jitter(0.5))
        pyautogui.press("enter")
        self._log("Character selected, loading world...")
        self._wait_ingame(timeout=self.INGAME_TIMEOUT)
        time.sleep(_jitter(1.2))
        self._log("In-game.")

    def logout(self, return_to_login: bool = False):
        """Exit the game with Ctrl+Q. If return_to_login, press Escape to go back to login."""
        self._focus()
        time.sleep(_jitter(0.5))
        pyautogui.hotkey("ctrl", "q")
        time.sleep(_jitter(3.0, pct=0.2))
        if return_to_login:
            pyautogui.press("escape")
            time.sleep(_jitter(0.5))
            self._log("Logout complete, client on login screen.")
        else:
            self._log("Logout complete.")

    # ------------------------------------------------------------------ #
    #  Gameplay
    # ------------------------------------------------------------------ #

    def drink_mana_potion(self):
        """Use a mana potion via F2 and wait for it to take effect."""
        self._focus()
        time.sleep(_jitter(0.3))
        pyautogui.press("f2")
        time.sleep(_jitter(3.5, pct=0.15))
        self._log("Mana potion used (F2).")

    def cast_exiva(self, target_name: str):
        """Open chat and cast exiva on target_name."""
        self._focus()
        time.sleep(_jitter(0.4))
        pyautogui.press("enter")
        time.sleep(_jitter(0.35))
        pyautogui.typewrite(f'exiva "{target_name}"', interval=_typing_interval())
        time.sleep(_jitter(0.3))
        pyautogui.press("enter")
        self._log(f"Exiva cast: {target_name}")

    def save_server_log(self, tab_x: int, tab_y: int, save_x: int, save_y: int):
        """Right-click the Server Log tab, then click 'Save window'."""
        self._focus()
        time.sleep(_jitter(0.4))
        move_mouse_like_human(tab_x, tab_y)
        time.sleep(_jitter(0.15))
        pyautogui.rightClick()
        time.sleep(_jitter(0.5))
        move_mouse_like_human(save_x, save_y)
        time.sleep(_jitter(0.15))
        pyautogui.click()
        time.sleep(_jitter(0.4))
        self._log("Server Log saved.")

    # ------------------------------------------------------------------ #
    #  Helpers
    # ------------------------------------------------------------------ #

    def _focus(self, timeout: float = 15.0):
        """Activate the Tibia window and wait until it actually has focus."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            win = self._get_window()
            if win:
                try:
                    win.activate()
                except Exception:
                    # pygetwindow may raise ERROR_INVALID_HANDLE (code 6) as a
                    # false positive: ShowWindow leaves a residual error on the thread
                    # and SetForegroundWindow returns 0 even when it succeeded.
                    # Verify real focus via _foreground_window_title instead of
                    # propagating the exception.
                    pass
                time.sleep(0.3)
                if "Tibia" in _foreground_window_title():
                    time.sleep(_jitter(0.2))
                    return
            time.sleep(0.2)
        raise RuntimeError("Could not focus the Tibia window.")

    def _get_window(self):
        wins = gw.getWindowsWithTitle("Tibia")
        return wins[0] if wins else None

    def _wait_for_window(self, title: str, timeout: int = 60):
        deadline = time.time() + timeout
        last_diagnostic = time.time()
        while time.time() < deadline:
            wins = gw.getWindowsWithTitle(title)
            if wins:
                wins[0].activate()
                return wins[0]
            # Diagnostic every 10s: show all visible titles to detect if the
            # client opened with an unexpected title.
            if time.time() - last_diagnostic >= 10:
                all_titles = [w.title for w in gw.getAllWindows() if w.title.strip()]
                self._log(f"[WAIT] Open windows: {all_titles}")
                last_diagnostic = time.time()
            time.sleep(0.5)
        raise TimeoutError(f"Window '{title}' did not appear within {timeout}s.")

    def _wait_ingame(self, timeout: int = 40):
        """The title changes to 'Tibia - CharacterName' when in-game."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            win = self._get_window()
            if win and " - " in win.title:
                return
            time.sleep(1)
        self._log("[WARN] Title did not change, continuing anyway.")

    def _log(self, msg: str):
        print(f"[Client] {msg}")
