"""Tests for the desktop launcher's server startup and browser fallback."""

from __future__ import annotations

import builtins
import time
import urllib.request

import pytest

from touchline.desktop import launcher


def test_start_server_serves_http(save_dir):
    port, _thread = launcher.start_server()
    url = f"http://127.0.0.1:{port}/saves"
    for _ in range(50):
        try:
            with urllib.request.urlopen(url, timeout=1) as resp:
                assert resp.status == 200
                return
        except Exception:
            time.sleep(0.1)
    pytest.fail("launcher server did not come up")


def test_open_window_falls_back_to_browser(monkeypatch):
    calls: dict[str, object] = {}

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "webview":
            raise ImportError("no web engine available")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    monkeypatch.setattr(launcher.webbrowser, "open",
                        lambda url: calls.__setitem__("url", url))

    class DummyThread:
        def join(self):
            calls["joined"] = True

    launcher.open_window("http://127.0.0.1:12345", DummyThread())

    assert calls["url"] == "http://127.0.0.1:12345"
    assert calls.get("joined") is True
