# Touchline RPG

A text-based football (soccer) career-mode RPG. Create a young player and guide
their career one season at a time — training, matches, transfers, aging,
retirement — chasing glory. It runs as a local desktop app: a Python backend
serves a local web UI inside a native window.

The world is fully fictional (procedurally generated leagues, clubs, and
players). Match days use a stat-driven summary simulation: a scoreline, key
events, and a short recap with your player's personal stats — not
minute-by-minute commentary.

## Features

- **Create a player** — pick a name and position; you start as a raw teenager at
  a lower-league club.
- **Season loop** — advance week by week through preseason, a 22-match league
  campaign, and the offseason. Pick a training focus on non-match weeks.
- **Match simulation** — a Poisson scoreline driven by team strength and home
  advantage, with attributed goals/assists, cards, injuries, and a personal
  rating and recap for your fixtures.
- **Progression** — young players grow toward their potential through training
  and minutes; veterans decline (legs first) and eventually retire.
- **Leagues** — a 3-tier, 12-clubs-per-tier pyramid with promotion and
  relegation, standings, and fixtures.
- **Transfers** — perform well in a window and rival clubs come calling;
  accept, reject, or counter their wage offer.
- **Save slots** — multiple independent careers, each an SQLite file; quit and
  resume exactly where you left off.

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
platform's web engine is unavailable, it falls back to opening your default
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

## Architecture

The game logic is a pure, UI-agnostic core with framework code kept at the edges:

- `touchline/engine/` — pure domain model and game logic (no Flask, SQLAlchemy,
  or pywebview). All randomness flows through an injected `random.Random`, so
  the whole game is deterministic under test.
- `touchline/persistence/` — SQLite persistence via SQLAlchemy (the only package
  that imports it); ORM rows are mapped to/from the engine's plain dataclasses.
- `touchline/web/` — a thin Flask layer: each route loads the active career,
  calls the engine, persists, and renders a template. Jinja2 + Pico.css, with
  htmx progressively enhancing the Advance Week action.
- `touchline/desktop/` — the `pywebview` launcher (Flask in a thread + a native
  window, with a browser fallback).

See [`PLAN.md`](PLAN.md) for the full architecture and design rationale.

## Save games

Careers are stored as individual SQLite files in a per-user data directory
(resolved via `platformdirs`). Set `TOUCHLINE_SAVE_DIR` to override the location.
