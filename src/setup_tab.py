"""
Calibration script — run ONCE (or whenever the UI changes).
Saves to config.json:
  - server_log_tab : position of the "Server Log" tab
  - save_window_pos: position of the "Save window" option in the context menu

Usage:
    python setup_tab.py
"""
import json
import os
import pyautogui

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "config.json")


def main():
    print("=" * 50)
    print("TibiaFinder Calibration")
    print("=" * 50)

    # --- STEP 1: Server Log tab ---
    print()
    print("STEP 1 — 'Server Log' tab")
    print("  1. Open Tibia and log in with any character")
    print("  2. Hover your mouse over the 'Server Log' tab")
    print("  3. Switch back to this window and press ENTER")
    print()
    input("Ready? Press ENTER...")

    tab_pos = pyautogui.position()
    print(f"  -> Tab captured: x={tab_pos.x}, y={tab_pos.y}")

    # --- STEP 2: "Save window" option ---
    print()
    print("STEP 2 — 'Save window' option in the context menu")
    print("  1. Right-click the 'Server Log' tab in Tibia")
    print("  2. Hover over the 'Save window' option (DO NOT click)")
    print("  3. Switch back to this window and press ENTER")
    print("  (IMPORTANT: keep the context menu open)")
    print()
    input("Ready? Press ENTER...")

    save_pos = pyautogui.position()
    print(f"  -> Save window captured: x={save_pos.x}, y={save_pos.y}")

    # --- Save to config ---
    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = json.load(f)

    cfg["server_log_tab"]  = {"x": tab_pos.x,  "y": tab_pos.y}
    cfg["save_window_pos"] = {"x": save_pos.x, "y": save_pos.y}

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

    print()
    print("Saved to config.json.")
    print("You can now start the API: uvicorn api:app --reload")


if __name__ == "__main__":
    main()
