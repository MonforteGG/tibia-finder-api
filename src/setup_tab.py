"""
Calibration script — run ONCE (or whenever the UI changes).
Saves to config.json:
  - server_log_tab      : position of the "Server Log" tab
  - save_window_pos     : position of the "Save window" option in the context menu
  - general_log_tab     : position of the general chat tab
  - general_log_save_pos: position of the "Save window" option for the general chat

Usage:
    python setup_tab.py
"""
import json
import os
import pyautogui

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "config.json")


def capture(prompt_lines: list[str]) -> pyautogui.Point:
    print()
    for line in prompt_lines:
        print(line)
    print()
    input("Ready? Press ENTER...")
    pos = pyautogui.position()
    print(f"  -> Captured: x={pos.x}, y={pos.y}")
    return pos


def main():
    print("=" * 50)
    print("TibiaFinder Calibration")
    print("=" * 50)

    # --- STEP 1: Server Log tab ---
    print("\nSTEP 1 — 'Server Log' tab")
    tab_pos = capture([
        "  1. Open Tibia and log in with any character",
        "  2. Hover your mouse over the 'Server Log' tab",
        "  3. Switch back to this window and press ENTER",
    ])

    # --- STEP 2: "Save window" option (Server Log) ---
    print("\nSTEP 2 — 'Save window' option for Server Log")
    save_pos = capture([
        "  1. Right-click the 'Server Log' tab in Tibia",
        "  2. Hover over the 'Save window' option (DO NOT click)",
        "  3. Switch back to this window and press ENTER",
        "  (IMPORTANT: keep the context menu open)",
    ])

    # --- STEP 3: General chat tab ---
    print("\nSTEP 3 — General chat tab")
    general_tab_pos = capture([
        "  1. Hover your mouse over the general/default chat tab in Tibia",
        "  2. Switch back to this window and press ENTER",
    ])

    # --- STEP 4: "Save window" option (General chat) ---
    print("\nSTEP 4 — 'Save window' option for General chat")
    general_save_pos = capture([
        "  1. Right-click the general chat tab in Tibia",
        "  2. Hover over the 'Save window' option (DO NOT click)",
        "  3. Switch back to this window and press ENTER",
        "  (IMPORTANT: keep the context menu open)",
    ])

    # --- Save to config ---
    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = json.load(f)

    cfg["server_log_tab"]       = {"x": tab_pos.x,          "y": tab_pos.y}
    cfg["save_window_pos"]      = {"x": save_pos.x,         "y": save_pos.y}
    cfg["general_log_tab"]      = {"x": general_tab_pos.x,  "y": general_tab_pos.y}
    cfg["general_log_save_pos"] = {"x": general_save_pos.x, "y": general_save_pos.y}

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

    print()
    print("Saved to config.json.")
    print("You can now start the API: uvicorn api:app --reload")


if __name__ == "__main__":
    main()
