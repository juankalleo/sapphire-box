from __future__ import annotations

import base64
import json
import os
import threading
import traceback
from typing import Any

_lock = threading.RLock()
_client: Any | None = None
_configured_dirs: tuple[str, str] | None = None


def _configure_paths(data_dir: str, cache_dir: str) -> None:
    os.environ["SAPPHIREBOX_DATA_DIR"] = data_dir
    os.environ["SAPPHIREBOX_CACHE_DIR"] = cache_dir
    os.environ["HOME"] = data_dir
    os.environ["TMPDIR"] = cache_dir

    from sapphirebox.core.config import initialize_app_paths

    initialize_app_paths()


def _get_client(data_dir: str, cache_dir: str) -> Any:
    global _client, _configured_dirs

    dirs = (data_dir, cache_dir)
    if _client is None or _configured_dirs != dirs:
        _configure_paths(data_dir, cache_dir)

        from fastapi.testclient import TestClient

        from sapphirebox.web.server import app

        _client = TestClient(app)
        _configured_dirs = dirs
    return _client


def _is_text_response(content_type: str) -> bool:
    content_type = content_type.lower()
    return (
        content_type.startswith("text/")
        or "application/json" in content_type
        or "application/javascript" in content_type
        or "application/xml" in content_type
        or "image/svg+xml" in content_type
    )


def _response_headers(response: Any) -> dict[str, str]:
    allowed = {
        "cache-control",
        "content-disposition",
        "content-length",
        "content-type",
        "etag",
        "last-modified",
    }
    return {
        key.lower(): value
        for key, value in response.headers.items()
        if key.lower() in allowed
    }


def _response_payload(response: Any) -> dict[str, Any]:
    headers = _response_headers(response)
    content_type = headers.get("content-type", "")
    body = response.content or b""
    payload: dict[str, Any] = {
        "status": response.status_code,
        "statusText": response.reason_phrase or "OK",
        "headers": headers,
    }

    if not body:
        payload["body"] = ""
    elif _is_text_response(content_type):
        encoding = response.encoding or "utf-8"
        payload["body"] = body.decode(encoding, errors="replace")
    else:
        payload["bodyBase64"] = base64.b64encode(body).decode("ascii")

    return payload


def _error_payload(error: BaseException) -> dict[str, Any]:
    detail = str(error) or error.__class__.__name__
    return {
        "status": 500,
        "statusText": "Android bridge error",
        "headers": {"content-type": "application/json; charset=utf-8"},
        "body": json.dumps(
            {"detail": detail, "traceback": traceback.format_exc()},
            ensure_ascii=False,
        ),
    }


def handle(data_dir: str, cache_dir: str, payload_json: str) -> str:
    """Handle a Sapphire Box web API request without starting a local server."""
    with _lock:
        try:
            payload = json.loads(payload_json or "{}")
            method = str(payload.get("method") or "GET").upper()
            url = str(payload.get("url") or "/api/health")
            body = payload.get("body")
            content = None if body is None else str(body).encode("utf-8")
            headers = {"content-type": "application/json"} if content is not None else None

            client = _get_client(data_dir, cache_dir)
            response = client.request(method, url, content=content, headers=headers)
            return json.dumps(_response_payload(response), ensure_ascii=False)
        except Exception as error:
            return json.dumps(_error_payload(error), ensure_ascii=False)


def start(data_dir: str, cache_dir: str) -> str:
    """Compatibility shim for older native shells; this does not start a server."""
    with _lock:
        _get_client(data_dir, cache_dir)
    return "https://appassets.androidplatform.net/assets/web/index.html"
