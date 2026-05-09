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
