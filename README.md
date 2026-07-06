# Touchline RPG

A text-based football career-mode RPG. Create a young player and take them
through their career one season at a time. Runs as a local desktop app (Python
backend, local web UI). The world is fully fictional and procedurally generated.

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

Opens a native window (via `pywebview`), falling back to your browser if no
system web engine is available. On Linux, install WebKitGTK for the native
window.

## Test

```bash
pytest
```

See [`PLAN.md`](PLAN.md) for architecture.
