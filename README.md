# TibiaFinder API

Local REST API that automates the Tibia client to cast `exiva` from multiple scout characters positioned in different cities, returning raw direction and distance readings for a target character.

## How it works

1. **Online check** — queries [TibiaData](https://tibiadata.com) to verify the target is online. If TibiaData is unavailable the search continues anyway.
2. **Client automation** — opens the Tibia client (or reuses it if already running), logs in with the first scout character, and casts `exiva "Target"` from their city.
3. **Log reading** — after each cast the Server Log is saved to disk and parsed for the exiva response (direction + distance).
4. **Mana check** — if no exiva response is found, casts a secondary spell (default `utevo lux`) and checks the Local Chat log. If the spell appears, the character had mana and the target is simply offline — search stops immediately. If the spell does not appear, a mana potion is used and the cast is retried (up to 3 times).
5. **Next character** — after logging out with `Ctrl+Q`, the next scout logs in from their city and repeats the process.
6. **Response** — all readings are returned as JSON with direction, distance, and the temple coordinates of each scout's city.

> **Windows only.** The automation layer relies on Win32 APIs (focus stealing via `AttachThreadInput`, window detection via `GetWindowThreadProcessId`) and pyautogui.

---

## Requirements

- Windows 10/11
- Python 3.10+
- Tibia client installed
- One Tibia account with multiple characters positioned in different cities (one per city you want to scout from)

---

## Installation

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

---

## Configuration

Edit `src/config/config.json`:

```json
{
  "world": "Vunira",
  "email": "your@email.com",
  "password": "yourpassword",
  "tibia_executable": "C:\\Users\\You\\AppData\\Local\\Tibia\\Tibia.exe",
  "client_load_seconds": 20,
  "mana_check_spell": "utevo lux",
  "mana_potion_key": "f2",
  "characters": [
    {
      "name": "Scout One",
      "char_index": 0,
      "city": "Venore"
    },
    {
      "name": "Scout Two",
      "char_index": 1,
      "city": "Ab'Dendriel"
    },
    {
      "name": "Scout Three",
      "char_index": 2,
      "city": "Thais"
    }
  ]
}
```

| Field | Description |
|---|---|
| `world` | Tibia world name (used for the online check) |
| `email` / `password` | Login credentials for the Tibia account |
| `tibia_executable` | Full path to `Tibia.exe` |
| `client_load_seconds` | Seconds to wait for the login screen after launch |
| `mana_check_spell` | Spell used to verify mana after a failed exiva (default: `utevo lux`) |
| `mana_potion_key` | Hotkey bound to a mana potion (default: `f2`) |
| `characters[].char_index` | Position of the character in the character list (0-indexed) |
| `characters[].city` | City where this character is stationed (must be a supported city) |

### Supported cities

Thais, Carlin, Venore, Edron, Ab'Dendriel, Kazordoon, Ankrahmun, Darashia, Liberty Bay, Port Hope, Svargrond, Yalahar.

---

## Calibration

Before the first run, calibrate the UI element positions so the automation knows where to click:

```bash
cd src
python setup_tab.py
```

This walks you through 4 steps:

1. Hover over the **Server Log** tab → press Enter
2. Right-click the Server Log tab, hover over **Save window** → press Enter
3. Hover over the **Local Chat** tab → press Enter
4. Right-click the Local Chat tab, hover over **Save window** → press Enter

Positions are saved automatically to `config.json`.

> Repeat calibration if you move or resize the Tibia UI.

---

## Running the API

```bash
cd src
venv\Scripts\uvicorn api:app --reload --port 8000
```

To use a different port:

```bash
venv\Scripts\uvicorn api:app --reload --port 8001
```

Press **Ctrl+C** to stop. The Tibia client will be closed automatically.

---

## API Reference

### `GET /finder/{target}`

Runs the full exiva search flow for the given character name.

**Example:**
```
GET http://localhost:8000/finder/Bubble
```

**Response:**
```json
{
  "target": "Bubble",
  "level": 412,
  "vocation": "Elite Knight",
  "is_online": true,
  "error": null,
  "readings": [
    {
      "character": "Scout One",
      "city": "Venore",
      "x": 32958,
      "y": 32076,
      "direction": "NW",
      "distance": "far"
    },
    {
      "character": "Scout Two",
      "city": "Ab'Dendriel",
      "x": 32732,
      "y": 31632,
      "direction": "S",
      "distance": "very_far"
    }
  ]
}
```

| Field | Values |
|---|---|
| `direction` | `N`, `NE`, `E`, `SE`, `S`, `SW`, `W`, `NW`, `here` |
| `distance` | `close` (5–100 sqm), `far` (101–249 sqm), `very_far` (250+ sqm) |
| `x`, `y` | Temple coordinates of the scout's city (Tibia coordinate system) |

**Error cases:**

| `is_online` | `error` | Meaning |
|---|---|---|
| `false` | `'Name' is not online in 'World'.` | Target offline (confirmed by TibiaData) |
| `true` | `No valid readings obtained.` | All scouts failed (mana, disconnection, etc.) |
| — | HTTP 409 | Another search is already in progress |

---

### `GET /health`

```json
{ "status": "ok", "world": "Vunira" }
```

---

## Architecture

```
src/
├── api.py              # FastAPI app, endpoints, search orchestration
├── setup_tab.py        # One-time UI calibration script
├── exiva_parser.py     # Parses raw exiva messages into structured data
├── tibiadata.py        # TibiaData API client (online check)
├── config/
│   └── config.json
└── utils/
    ├── client.py       # Tibia client automation (login, exiva, logout)
    ├── log_reader.py   # Reads Server Log and Local Chat log files
    └── human_movement.py
```

**Threading model:** all GUI operations (pyautogui, pygetwindow) run on a single dedicated thread to guarantee the Windows desktop context. The FastAPI async layer submits work via a queue and awaits the result.

---

## Notes

- Only one search can run at a time. Concurrent requests receive HTTP 409.
- Characters are cycled sequentially: first character does a full login, subsequent ones use `Ctrl+Q` → character select → Enter.
- The Tibia client is left open between searches at the login screen.
- The `exiva` distance uses Chebyshev distance: `max(|dx|, |dy|)`.
