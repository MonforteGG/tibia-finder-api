"""
Reads Tibia's Server Log.txt and extracts the most recent exiva response.
"""
import os
import time
from typing import Optional

from exiva_parser import ExivaResult, parse as parse_exiva

LOG_PATH = os.path.join(
    os.environ["LOCALAPPDATA"],
    "Tibia", "packages", "Tibia", "log", "Server Log.txt"
)

GENERAL_LOG_PATH = os.path.join(
    os.environ["LOCALAPPDATA"],
    "Tibia", "packages", "Tibia", "log", "Local Chat.txt"
)


def read_new_lines(since_size: int) -> list[str]:
    """Returns lines appended to the file since `since_size` bytes."""
    if not os.path.exists(LOG_PATH):
        return []
    with open(LOG_PATH, encoding="utf-8", errors="ignore") as f:
        f.seek(since_size)
        return f.readlines()


def current_size() -> int:
    if not os.path.exists(LOG_PATH):
        return 0
    return os.path.getsize(LOG_PATH)


def current_general_size() -> int:
    if not os.path.exists(GENERAL_LOG_PATH):
        return 0
    return os.path.getsize(GENERAL_LOG_PATH)


def read_new_general_lines(since_size: int) -> list[str]:
    if not os.path.exists(GENERAL_LOG_PATH):
        return []
    with open(GENERAL_LOG_PATH, encoding="utf-8", errors="ignore") as f:
        f.seek(since_size)
        return f.readlines()


def wait_for_spell(spell: str, since_size: int, timeout: float = 5.0) -> bool:
    """Returns True if the spell text appears in the general chat log."""
    spell_lower = spell.lower()
    deadline = time.time() + timeout
    while time.time() < deadline:
        for line in read_new_general_lines(since_size):
            if spell_lower in line.lower():
                return True
        time.sleep(0.3)
    return False


def wait_for_exiva(target: str, since_size: int, timeout: float = 8.0) -> Optional[ExivaResult]:
    """Wait up to `timeout` seconds for the exiva response to appear in the log."""
    target_lower = target.lower()
    deadline = time.time() + timeout
    while time.time() < deadline:
        for line in read_new_lines(since_size):
            if target_lower in line.lower():
                result = parse_exiva(line.strip())
                if result:
                    return result
        time.sleep(0.3)
    return None
