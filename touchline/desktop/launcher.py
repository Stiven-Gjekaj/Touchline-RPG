"""Desktop launcher: run the Flask app in a native window via pywebview.

Starts Flask on a free localhost port in a daemon thread, then opens a
pywebview window pointed at it. If pywebview (or its OS web engine) is
unavailable, falls back to opening the user's default browser so the game is
never fully blocked by a missing system component.

Heavy imports (Flask, pywebview) are performed lazily inside ``main`` so the
module can be imported cheaply — e.g. by ``run.py`` — without them installed.
"""

from __future__ import annotations

import socket
import threading
import webbrowser


def _free_port() -> int:
    """Return an unused TCP port on the loopback interface."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def main() -> None:
    """Launch the desktop app (native window, with browser fallback)."""
    from touchline.web import create_app

    app = create_app()
    port = _free_port()

    # Bind to 127.0.0.1 only: this is a local single-user app, never a network
    # service. use_reloader=False is required because Werkzeug's reloader
    # re-execs the process, which breaks when Flask runs on a background thread.
    thread = threading.Thread(
        target=lambda: app.run(
            host="127.0.0.1", port=port, debug=False, use_reloader=False, threaded=True
        ),
        daemon=True,
    )
    thread.start()

    url = f"http://127.0.0.1:{port}"
    try:
        import webview  # type: ignore[import-not-found]

        webview.create_window(
            "Touchline RPG", url, width=1200, height=800, min_size=(900, 600)
        )
        webview.start()
    except Exception:  # pragma: no cover - depends on OS web engine availability
        webbrowser.open(url)
        thread.join()
