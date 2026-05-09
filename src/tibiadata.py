"""
Client for TibiaData API v4.
https://api.tibiadata.com/v4/

Used to verify whether a character is online on a given world and to fetch
basic character info (level, vocation).
"""

import httpx
from dataclasses import dataclass
from typing import Optional


TIBIADATA_BASE = "https://api.tibiadata.com/v4"
# TibiaData caches the world online list — typically every ~60 seconds.
_REQUEST_TIMEOUT = 10.0


class TibiaDataError(Exception):
    """Raised when the TibiaData API returns an unexpected response."""


@dataclass
class PlayerStatus:
    is_online: bool
    level: Optional[int] = None
    vocation: Optional[str] = None


async def get_player_status(player_name: str, world: str) -> PlayerStatus:
    """
    Return online status, level and vocation for `player_name` in `world`.

    Uses GET /v4/world/{world} which includes level and vocation for each
    online player. Comparison is case-insensitive.

    Raises:
        TibiaDataError: if the HTTP request fails or the response is malformed.
    """
    url = f"{TIBIADATA_BASE}/world/{world}"
    try:
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
            resp = await client.get(url)
            resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise TibiaDataError(
            f"TibiaData responded with {e.response.status_code} for world '{world}'"
        ) from e
    except httpx.RequestError as e:
        raise TibiaDataError(f"Could not reach TibiaData API: {e}") from e

    try:
        data = resp.json()
        online_players: list = data["world"]["online_players"] or []
    except (KeyError, TypeError, ValueError) as e:
        raise TibiaDataError(f"Unexpected TibiaData response structure: {e}") from e

    name_lower = player_name.lower()
    for p in online_players:
        if p["name"].lower() == name_lower:
            return PlayerStatus(
                is_online=True,
                level=p.get("level"),
                vocation=p.get("vocation"),
            )
    return PlayerStatus(is_online=False)
