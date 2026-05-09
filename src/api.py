"""
TibiaFinder API — FastAPI

POST /find
    Full flow: verifies online status, opens the Tibia client, casts exiva with
    each character sequentially, and returns the raw readings.

POST /parse
    Parses an exiva message and returns the structured data.

GET /cities
    Lists all cities with known temple positions.
"""

import asyncio
import concurrent.futures
import json
import os
import queue
import sys
import time
import threading

sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional

from exiva_parser import parse as parse_exiva
from tibiadata import get_player_status, TibiaDataError

# Known temple positions for major cities {city: (x, y, z)}.
# Tibia coordinate system: X increases East, Y increases South, Z=7 is ground floor outdoors.
TEMPLE_POSITIONS = {
    "Thais":        (32369, 32241, 7),
    "Carlin":       (32360, 31782, 7),
    "Venore":       (32958, 32076, 7),
    "Edron":        (33219, 31862, 7),
    "Ab'Dendriel":  (32732, 31632, 7),
    "Kazordoon":    (32649, 31925, 7),
    "Ankrahmun":    (32726, 32630, 7),
    "Darashia":     (33196, 32455, 7),
    "Liberty Bay":  (32325, 32600, 7),
    "Port Hope":    (32594, 32694, 7),
    "Svargrond":    (32548, 31467, 7),
    "Yalahar":      (32777, 31521, 7),
}

# ── Config ─────────────────────────────────────────────────────────────────────

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "config.json")


def _load_config() -> dict:
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def _load_world() -> str:
    try:
        return _load_config().get("world", "Antica")
    except Exception:
        return "Antica"


# ── App ────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="TibiaFinder API",
    description="Triangulates a Tibia character's position using exiva readings.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dedicated GUI thread — lives for the full lifetime of the app and is the only
# thread that touches pyautogui/pygetwindow. A generic thread pool does not
# guarantee the Windows desktop context required for GUI automation.
_gui_queue: queue.Queue = queue.Queue()


def _gui_worker() -> None:
    while True:
        item = _gui_queue.get()
        if item is None:
            break
        func, args, future = item
        try:
            result = func(*args)
            if not future.cancelled():
                future.set_result(result)
        except Exception as exc:
            if not future.cancelled():
                future.set_exception(exc)


_gui_thread = threading.Thread(target=_gui_worker, daemon=True, name="tibiafinder-gui")
_gui_thread.start()

# Global lock: rejects a second search while one is already running.
_find_lock = threading.Lock()


# ── Models ─────────────────────────────────────────────────────────────────────


class FindRequest(BaseModel):
    target: str = Field(
        ..., description="Exact name of the character to search for.", examples=["Bubble"]
    )


class ParsedReading(BaseModel):
    message: str
    target_name: str
    is_here: bool
    is_above: bool
    is_below: bool
    direction: Optional[str]
    distance_qualifier: str
    floor_qualifier: Optional[str]
    distance_range_sqm: Optional[tuple]


class ReadingDetail(BaseModel):
    character: str
    city: Optional[str] = None
    x: int
    y: int
    direction: str  # "N"|"NE"|"E"|"SE"|"S"|"SW"|"W"|"NW"|"here"
    distance: str   # "close"|"far"|"very_far"


class FindResponse(BaseModel):
    target: str
    level: Optional[int] = None
    vocation: Optional[str] = None
    is_online: bool
    error: Optional[str] = None
    readings: List[ReadingDetail] = []


class ParseResponse(BaseModel):
    ok: bool
    parsed: Optional[ParsedReading]
    error: Optional[str] = None


class ParseRequest(BaseModel):
    message: str = Field(..., description="Raw exiva message from the server log.")


# ── Helpers ───────────────────────────────────────────────────────────────────


def _to_parsed_reading(msg: str, result) -> ParsedReading:
    return ParsedReading(
        message=msg,
        target_name=result.target_name,
        is_here=result.is_here,
        is_above=result.is_above,
        is_below=result.is_below,
        direction=result.direction,
        distance_qualifier=result.distance_qualifier,
        floor_qualifier=result.floor_qualifier,
        distance_range_sqm=result.distance_range,
    )


_DIR_ABBREV = {
    "north": "N", "north-east": "NE", "east": "E", "south-east": "SE",
    "south": "S", "south-west": "SW", "west": "W", "north-west": "NW",
}


def _reading_detail(name: str, city: str, cx: int, cy: int, result) -> ReadingDetail:
    if result.is_here:
        return ReadingDetail(character=name, city=city, x=cx, y=cy, direction="here", distance="close")
    return ReadingDetail(
        character=name,
        city=city,
        x=cx,
        y=cy,
        direction=_DIR_ABBREV.get(result.direction or "", "?"),
        distance=result.distance_qualifier or "very_far",
    )


def _run_find(
    target: str,
    cfg: dict,
    level: Optional[int] = None,
    vocation: Optional[str] = None,
) -> FindResponse:
    """
    Blocking flow (pyautogui). Runs in a dedicated thread.
    For each character:
      - First character: full login (password + character selection)
      - Subsequent characters: character selection only (already at char select after logout)
    The client is never closed.
    """
    from utils.client import Client
    from utils.log_reader import current_size, wait_for_exiva

    MAX_MANA_RETRIES = 3
    tab = cfg.get("server_log_tab")
    save = cfg.get("save_window_pos")
    characters = cfg["characters"]

    if not tab or not save:
        return FindResponse(
            target=target,
            level=level,
            vocation=vocation,
            is_online=True,
            error="Missing server_log_tab or save_window_pos in config.json. Run setup_tab.py first.",
        )

    reading_details: list[ReadingDetail] = []
    first_char = True

    for i, char_cfg in enumerate(characters):
        city = char_cfg["city"]
        client = Client(
            executable=cfg["tibia_executable"],
            email=cfg["email"],
            password=cfg["password"],
            char_index=char_cfg["char_index"],
            load_seconds=cfg.get("client_load_seconds", 20),
        )

        try:
            client.start()

            if first_char:
                client.login()
                first_char = False
            else:
                client.select_character()

            time.sleep(1.5)

            # Cast exiva with retries for out-of-mana situations
            result = None
            for attempt in range(MAX_MANA_RETRIES + 1):
                size_before = current_size()
                client.cast_exiva(target)
                time.sleep(2.5)
                client.save_server_log(tab["x"], tab["y"], save["x"], save["y"])
                result = wait_for_exiva(target, size_before, timeout=6.0)

                if result:
                    break

                if attempt < MAX_MANA_RETRIES:
                    print(
                        f"[WARN] Out of mana in {city}, using mana potion F2... ({attempt + 1}/{MAX_MANA_RETRIES})"
                    )
                    client.drink_mana_potion()
                else:
                    print(
                        f"[WARN] No exiva response in {city} after all retries."
                    )

            is_last = i == len(characters) - 1
            client.logout(return_to_login=is_last)

        except Exception as e:
            print(f"[ERROR] Character in {city}: {e}")
            try:
                is_last = i == len(characters) - 1
                client.logout(return_to_login=is_last)
            except Exception:
                pass
            continue

        if result is None:
            continue

        pos = TEMPLE_POSITIONS.get(city)
        if pos is None:
            print(f"[WARN] Unknown position for {city}.")
            continue

        cx = pos["x"] if isinstance(pos, dict) else pos[0]
        cy = pos["y"] if isinstance(pos, dict) else pos[1]
        char_name = char_cfg.get("name", city)
        reading_details.append(_reading_detail(char_name, city, cx, cy, result))

    if not reading_details:
        return FindResponse(
            target=target,
            level=level,
            vocation=vocation,
            is_online=True,
            error="No valid readings obtained.",
        )

    return FindResponse(
        target=target,
        level=level,
        vocation=vocation,
        is_online=True,
        readings=reading_details,
        error=None,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────


async def _find(target: str) -> FindResponse:
    world = _load_world()

    try:
        status = await get_player_status(target, world)
    except TibiaDataError as e:
        raise HTTPException(status_code=503, detail=f"TibiaData unavailable: {e}")

    if not status.is_online:
        return FindResponse(
            target=target,
            is_online=False,
            error=f"'{target}' is not online in '{world}'.",
        )

    if not _find_lock.acquire(blocking=False):
        raise HTTPException(
            status_code=409,
            detail="A search is already in progress. Wait for it to finish.",
        )

    try:
        cfg = _load_config()
        cf_future: concurrent.futures.Future = concurrent.futures.Future()
        _gui_queue.put((_run_find, (target, cfg, status.level, status.vocation), cf_future))
        return await asyncio.wrap_future(cf_future)
    finally:
        _find_lock.release()


@app.get("/finder/{target}", response_model=FindResponse)
async def find_by_name(target: str):
    """Find a character by name (GET)."""
    return await _find(target)


@app.post("/find", response_model=FindResponse)
async def find_endpoint(body: FindRequest):
    """Find a character by name (POST with JSON body)."""
    return await _find(body.target)


@app.post("/parse", response_model=ParseResponse)
def parse_endpoint(body: ParseRequest):
    """Parse an exiva message."""
    message = body.message
    result = parse_exiva(message)
    if result is None:
        return ParseResponse(
            ok=False,
            error="Message does not match any known exiva format.",
        )
    return ParseResponse(ok=True, parsed=_to_parsed_reading(message, result))


@app.get("/health")
def health():
    return {"status": "ok", "world": _load_world()}
