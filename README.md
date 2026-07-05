# Touchline RPG

A text-based football (soccer) career-mode RPG. Create a young player and guide
their career one season at a time — training, matches, transfers, aging,
retirement — chasing glory. Runs as a local desktop app: a Python backend serves
a local web UI inside a native window.

The world is fully fictional (procedurally generated leagues, clubs, and
players). Match days use a stat-driven summary simulation: a scoreline, key
events, and a short recap with your player's personal stats — not minute-by-minute
commentary.

## Status

Under active development on `working/v1`. See [`PLAN.md`](PLAN.md) for the full
architecture and milestone breakdown.

## Requirements

- Python 3.11+

## Setup

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Run

```bash
python run.py
```

This starts the local server and opens a native window (via `pywebview`). If the
platform web engine is unavailable, it falls back to opening your default
browser.

### Linux note

`pywebview` needs a system web engine — install WebKitGTK
(e.g. `gir1.2-webkit2-4.1` / `gir1.2-webkit2-4.0` on Debian/Ubuntu) or a
Qt + QtWebEngine backend. Without one, the app still runs and falls back to your
browser.

## Tests

```bash
pytest
```

## Save games

Careers are stored as individual SQLite files in a per-user data directory
(resolved via `platformdirs`). Set `TOUCHLINE_SAVE_DIR` to override the location.
