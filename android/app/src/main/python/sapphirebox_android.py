from __future__ import annotations

import os
import threading
import time
import urllib.error
import urllib.request

HOST = "127.0.0.1"
PORT = 8765
URL = f"http://{HOST}:{PORT}"

_lock = threading.Lock()
_started = False


def _wait_until_ready() -> None:
    deadline = time.monotonic() + 25
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{URL}/api/health", timeout=1) as response:
                if 200 <= response.status < 500:
                    return
        except (OSError, urllib.error.URLError):
            time.sleep(0.25)
    raise RuntimeError("servidor local nao respondeu a tempo")


def _run_server() -> None:
    import uvicorn

    from sapphirebox.core.config import initialize_app_paths
    from sapphirebox.web.server import app

    initialize_app_paths()
    config = uvicorn.Config(app, host=HOST, port=PORT, log_level="warning", access_log=False)
    server = uvicorn.Server(config)
    server.run()


def start(data_dir: str, cache_dir: str) -> str:
    global _started

    os.environ["SAPPHIREBOX_DATA_DIR"] = data_dir
    os.environ["SAPPHIREBOX_CACHE_DIR"] = cache_dir
    os.environ["HOME"] = data_dir
    os.environ["TMPDIR"] = cache_dir

    with _lock:
        if not _started:
            thread = threading.Thread(target=_run_server, name="sapphirebox-web", daemon=True)
            thread.start()
            _started = True

    _wait_until_ready()
    return URL
