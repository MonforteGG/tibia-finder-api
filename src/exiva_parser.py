"""
Parser for Tibia exiva spell messages.

Based on TFS source: forgottenserver/data/scripts/spells/support/find_person.lua

Distance is Chebyshev: max(|dx|, |dy|)

Ranges:
    BESIDE:  1–4    sqm  → "is standing next to you" / "is above/below you"
    CLOSE:   5–100  sqm  → "is to the [dir]" / "is on a lower/higher level to the [dir]"
    FAR:   101–249  sqm  → "is far to the [dir]"
    VERYFAR: 250+   sqm  → "is very far to the [dir]"

Direction sectors (tangent-based, equivalent to ±22.5° per sector):
    |dy/dx| < 0.4142  → pure E/W
    |dy/dx| < 2.4142  → diagonal (NE/NW/SE/SW)
    |dy/dx| >= 2.4142 → pure N/S
"""

import re
from dataclasses import dataclass
from typing import Optional

# Chebyshev distance ranges per qualifier.
# Source: TFS find_person.lua — maxPositionDifference < 5 / < 101 / < 250 / else
DISTANCE_RANGES = {
    "beside": (1, 4),
    "close": (5, 100),
    "far": (101, 249),
    "very_far": (250, 2000),
}

DIRECTIONS = [
    "north-east",
    "north-west",
    "south-east",
    "south-west",
    "north",
    "south",
    "east",
    "west",
]

_DIR = "|".join(DIRECTIONS)

# All possible message formats from TFS:
#
#   [Name] is standing next to you.
#   [Name] is above you.
#   [Name] is below you.
#   [Name] is to the {dir}.
#   [Name] is on a lower level to the {dir}.
#   [Name] is on a higher level to the {dir}.
#   [Name] is far to the {dir}.
#   [Name] is very far to the {dir}.
#
# Offline: sendCancelMessage — does NOT appear in server log.

_PATTERN = re.compile(
    rf"^(.+?) "
    rf"("
    rf"is standing next to you"
    rf"|is above you"
    rf"|is below you"
    rf"|is to the ({_DIR})"
    rf"|is on a lower level to the ({_DIR})"
    rf"|is on a higher level to the ({_DIR})"
    rf"|is far to the ({_DIR})"
    rf"|is very far to the ({_DIR})"
    rf")\.$",
    re.IGNORECASE,
)


@dataclass
class ExivaResult:
    target_name: str
    raw_message: str
    # Positioning
    is_beside: bool = False  # 1–4 sqm (same floor)
    is_above: bool = False   # 1–4 sqm, caster is above target
    is_below: bool = False   # 1–4 sqm, caster is below target
    direction: Optional[str] = None  # e.g. "north-east"
    distance_qualifier: str = ""     # "close", "far", "very_far"
    floor_qualifier: Optional[str] = None  # None / "lower" / "higher"

    @property
    def is_here(self) -> bool:
        """True when target is within 4 sqm (any floor relation)."""
        return self.is_beside or self.is_above or self.is_below

    @property
    def distance_range(self) -> Optional[tuple]:
        if self.is_here:
            return DISTANCE_RANGES["beside"]
        return DISTANCE_RANGES.get(self.distance_qualifier)


def parse(message: str) -> Optional["ExivaResult"]:
    """
    Parse a raw exiva server-log message into a structured ExivaResult.

    Returns None if the message does not match any known exiva format.
    Note: offline messages (sendCancelMessage) never appear in the server log
    and therefore cannot be detected here.
    """
    m = _PATTERN.match(message.strip())
    if not m:
        return None

    name = m.group(1)

    if m.group(2).lower() == "is standing next to you":
        return ExivaResult(target_name=name, raw_message=message, is_beside=True)

    if m.group(2).lower() == "is above you":
        return ExivaResult(target_name=name, raw_message=message, is_above=True)

    if m.group(2).lower() == "is below you":
        return ExivaResult(target_name=name, raw_message=message, is_below=True)

    # Close — same floor
    if m.group(3):
        return ExivaResult(
            target_name=name,
            raw_message=message,
            direction=m.group(3).lower(),
            distance_qualifier="close",
        )

    # Close — lower floor
    if m.group(4):
        return ExivaResult(
            target_name=name,
            raw_message=message,
            direction=m.group(4).lower(),
            distance_qualifier="close",
            floor_qualifier="lower",
        )

    # Close — higher floor
    if m.group(5):
        return ExivaResult(
            target_name=name,
            raw_message=message,
            direction=m.group(5).lower(),
            distance_qualifier="close",
            floor_qualifier="higher",
        )

    # Far
    if m.group(6):
        return ExivaResult(
            target_name=name,
            raw_message=message,
            direction=m.group(6).lower(),
            distance_qualifier="far",
        )

    # Very far
    if m.group(7):
        return ExivaResult(
            target_name=name,
            raw_message=message,
            direction=m.group(7).lower(),
            distance_qualifier="very_far",
        )

    return None
