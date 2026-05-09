"""
tibiafinder — Triangulates a Tibia character's location using exiva.

Usage:
    python main.py <character_name>
"""

import json
import os
import sys
import time
from typing import Optional

sys.path.insert(0, os.path.dirname(__file__))

from utils.client import Client
from utils.log_reader import current_size, wait_for_exiva
from exiva_parser import ExivaResult
from triangulator import CasterReading, triangulate, TEMPLE_POSITIONS

MAX_MANA_RETRIES = 3

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "config.json")


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def perform_exiva(
    cfg: dict, char_cfg: dict, target: str, return_to_login: bool = False
) -> Optional[ExivaResult]:
    tab = cfg.get("server_log_tab")
    save = cfg.get("save_window_pos")
    if not tab:
        print(
            "[ERROR] Missing server_log_tab in config.json. Run setup_tab.py first."
        )
        return None
    if not save:
        print(
            "[ERROR] Missing save_window_pos in config.json. Run setup_tab.py first."
        )
        return None

    client = Client(
        executable=cfg["tibia_executable"],
        email=cfg["email"],
        password=cfg["password"],
        char_index=char_cfg["char_index"],
        load_seconds=cfg.get("client_load_seconds", 20),
    )

    result = None
    try:
        client.start()
        client.login()
        time.sleep(1.5)

        for attempt in range(MAX_MANA_RETRIES + 1):
            size_before = current_size()
            client.cast_exiva(target)
            time.sleep(2.5)

            client.save_server_log(tab["x"], tab["y"], save["x"], save["y"])
            result = wait_for_exiva(target, size_before, timeout=6.0)

            if result:
                print(f"[OK] {result.raw_message}")
                break

            if attempt < MAX_MANA_RETRIES:
                print(
                    f"[WARN] No exiva response (out of mana). "
                    f"Using mana potion F2... (attempt {attempt + 1}/{MAX_MANA_RETRIES})"
                )
                client.drink_mana_potion()
            else:
                print("[ERROR] No exiva response after all retries.")

        client.logout(return_to_login=return_to_login)
    except Exception as e:
        print(f"[ERROR] {e}")
        try:
            client.logout(return_to_login=return_to_login)
        except Exception:
            pass

    return result


def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py <character_name>")
        sys.exit(1)

    target = " ".join(sys.argv[1:])
    cfg = load_config()

    print(f"\n=== TibiaFinder: searching for '{target}' ===\n")

    readings: list[CasterReading] = []

    characters = cfg["characters"]
    for i, char_cfg in enumerate(characters):
        city = char_cfg["city"]
        print(f"--- Character in {city} ---")

        is_last = i == len(characters) - 1
        result = perform_exiva(cfg, char_cfg, target, return_to_login=is_last)

        if result is None:
            print(f"No reading for {city}.\n")
            continue

        pos = char_cfg.get("temple_position") or TEMPLE_POSITIONS.get(city)
        if pos is None:
            print(f"[WARN] Unknown position for {city}.\n")
            continue

        readings.append(
            CasterReading(
                city=city,
                caster_x=pos["x"] if isinstance(pos, dict) else pos[0],
                caster_y=pos["y"] if isinstance(pos, dict) else pos[1],
                result=result,
            )
        )
        print()

    if not readings:
        print("No readings. Check your configuration.")
        sys.exit(1)

    if all(r.result.is_here for r in readings):
        print(f"'{target}' is not in Tibia.")
        sys.exit(0)

    print("=== Triangulating... ===")
    area = triangulate(readings)

    if area is None:
        print("No consistent area found.")
        for r in readings:
            print(f"  {r.city}: {r.result.raw_message}")
    else:
        print(f"\n'{target}' is probably in:")
        print(f"  Center:  ({area.center_x}, {area.center_y})")
        print(f"  Area:    ({area.x_min},{area.y_min}) → ({area.x_max},{area.y_max})")
        print(f"  Zone of {area.x_max - area.x_min} x {area.y_max - area.y_min} tiles")


if __name__ == "__main__":
    main()
