"""Native desktop window for Sapphire Box.

Same FastAPI backend and bundled frontend as `sapphirebox web` — this
just opens it in a real OS window via `pywebview` instead of a browser tab.
One code path covers macOS, Linux and Windows: pywebview picks each
platform's own WebView (Cocoa WKWebView, GTK WebKit, WebView2), so there's
no per-OS project to maintain here — unlike Android, which genuinely
needs its own native shell (see android/).
"""
from __future__ import annotations

import threading
import time

import httpx
import uvicorn

from sapphirebox.core.resources import resource_path
from sapphirebox.web.server import app as fastapi_app

HOST = "127.0.0.1"
PORT = 8747
APP_ICON = resource_path("web", "assets", "app-icon.png")


def _run_server() -> None:
    uvicorn.run(fastapi_app, host=HOST, port=PORT, log_level="warning")


def _wait_until_ready(timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout
    url = f"http://{HOST}:{PORT}/api/health"
    while time.monotonic() < deadline:
        try:
            if httpx.get(url, timeout=1.0).status_code == 200:
                return True
        except httpx.HTTPError:
            pass
        time.sleep(0.2)
    return False


def main() -> None:
    try:
        import webview
    except ImportError as exc:
        raise RuntimeError(
            "pywebview não está instalado. Rode: pip install sapphirebox[desktop]"
        ) from exc

    threading.Thread(target=_run_server, daemon=True).start()
    if not _wait_until_ready():
        raise RuntimeError(f"O backend não respondeu em http://{HOST}:{PORT} a tempo")

    webview.create_window(
        "Sapphire Box",
        f"http://{HOST}:{PORT}",
        width=1180,
        height=760,
        min_size=(720, 480),
    )
    webview.start(icon=str(APP_ICON) if APP_ICON.exists() else None)


if __name__ == "__main__":
    main()
