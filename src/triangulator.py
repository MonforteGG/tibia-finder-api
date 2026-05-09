"""
Triangulator for Tibia exiva readings.

Based on TFS source: forgottenserver/data/scripts/spells/support/find_person.lua

Distance metric: Chebyshev — max(|dx|, |dy|)
This means each distance band forms a hollow SQUARE ring, not a circle.

Direction algorithm (tangent-based, equivalent to ±22.5° sectors):
    tangent = dy / dx  (if dx==0, sentinel=10 to force N/S)
    |tangent| < 0.4142  → pure E/W
    |tangent| < 2.4142  → diagonal NE/NW/SE/SW
    |tangent| >= 2.4142 → pure N/S
"""

import math
from dataclasses import dataclass
from typing import List, Optional

from exiva_parser import ExivaResult, DISTANCE_RANGES

# Tangent thresholds from TFS source
_TAN_22_5 = math.tan(math.radians(22.5))  # 0.4142
_TAN_67_5 = math.tan(math.radians(67.5))  # 2.4142

# Known temple positions for major cities {city: (x, y, z)}.
# Tibia coordinate system: X increases East, Y increases South, Z=7 is ground floor outdoors.
TEMPLE_POSITIONS = {
    "Thais": (32311, 32233, 7),
    "Carlin": (32360, 31782, 7),
    "Venore": (32934, 32076, 7),
    "Edron": (33219, 31862, 7),
    "Ab'Dendriel": (32710, 31642, 7),
    "Kazordoon": (32649, 31925, 7),
    "Ankrahmun": (32726, 32630, 7),
    "Darashia": (33196, 32455, 7),
    "Liberty Bay": (32325, 32600, 7),
    "Port Hope": (32594, 32694, 7),
    "Svargrond": (32548, 31467, 7),
    "Yalahar": (32777, 31521, 7),
}

# Approximate bounds of the Tibia main continent (ground floor).
MAP_X_MIN, MAP_X_MAX = 32000, 33600
MAP_Y_MIN, MAP_Y_MAX = 31000, 33000
GRID_STEP = 2  # tiles per grid cell (lower = finer, slower)


@dataclass
class CasterReading:
    """One exiva cast from a known position."""

    city: str
    caster_x: int
    caster_y: int
    result: ExivaResult


@dataclass
class Area:
    x_min: int
    y_min: int
    x_max: int
    y_max: int
    center_x: int
    center_y: int
    consistent_cells: int

    def __str__(self) -> str:
        return (
            f"Estimated area: ({self.x_min},{self.y_min}) → ({self.x_max},{self.y_max})  "
            f"Center: ({self.center_x},{self.center_y})  "
            f"Consistent cells: {self.consistent_cells}"
        )


def _chebyshev(cx: int, cy: int, tx: int, ty: int) -> int:
    """Chebyshev distance between two points (square/chessboard metric)."""
    return max(abs(tx - cx), abs(ty - cy))


def _tfs_direction(cx: int, cy: int, tx: int, ty: int) -> str:
    """
    Compute the exiva direction string from caster (cx,cy) to target (tx,ty).
    Replicates the TFS tangent-based algorithm exactly.
    Tibia Y increases southward.
    """
    dx = cx - tx  # positive → target is west
    dy = cy - ty  # positive → target is north

    tangent = (dy / dx) if dx != 0 else 10.0  # sentinel=10 forces N/S when dx=0

    if abs(tangent) < _TAN_22_5:
        # Pure E/W
        return "west" if dx > 0 else "east"
    elif abs(tangent) < _TAN_67_5:
        # Diagonal
        if tangent > 0:
            return "north-west" if dy > 0 else "south-east"
        else:
            return "south-west" if dx > 0 else "north-east"
    else:
        # Pure N/S
        return "north" if dy > 0 else "south"


def _cell_matches(tx: int, ty: int, reading: CasterReading) -> bool:
    """Return True if tile (tx,ty) is consistent with one exiva reading."""
    result = reading.result
    cx, cy = reading.caster_x, reading.caster_y

    dist = _chebyshev(cx, cy, tx, ty)

    if result.is_here:
        return dist <= 4

    if result.direction is None or result.distance_range is None:
        return False

    d_min, d_max = result.distance_range
    if not (d_min <= dist <= d_max):
        return False

    expected_dir = _tfs_direction(cx, cy, tx, ty)
    return expected_dir == result.direction


def triangulate(readings: List[CasterReading]) -> Optional[Area]:
    """
    Returns the estimated Area where the target is located.
    Only uses readings with actual directional data (skips beside/above/below
    readings from a single source as they give no direction info).
    Returns None if no consistent area is found.
    """
    useful = [r for r in readings if r.result.direction is not None or r.result.is_here]
    if not useful:
        return None

    consistent_xs = []
    consistent_ys = []

    for tx in range(MAP_X_MIN, MAP_X_MAX + 1, GRID_STEP):
        for ty in range(MAP_Y_MIN, MAP_Y_MAX + 1, GRID_STEP):
            if all(_cell_matches(tx, ty, r) for r in useful):
                consistent_xs.append(tx)
                consistent_ys.append(ty)

    if not consistent_xs:
        return None

    x_min, x_max = min(consistent_xs), max(consistent_xs)
    y_min, y_max = min(consistent_ys), max(consistent_ys)
    cx = (x_min + x_max) // 2
    cy = (y_min + y_max) // 2

    return Area(
        x_min=x_min,
        y_min=y_min,
        x_max=x_max,
        y_max=y_max,
        center_x=cx,
        center_y=cy,
        consistent_cells=len(consistent_xs),
    )
