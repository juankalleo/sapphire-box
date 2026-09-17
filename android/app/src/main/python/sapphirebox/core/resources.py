"""Access to files bundled inside the installed package."""
from __future__ import annotations

from contextlib import ExitStack
from importlib import resources
from pathlib import Path

_STACK = ExitStack()
_ASSETS_PACKAGE = "sapphirebox.assets"


def resource_path(*parts: str) -> Path:
    """Return a real filesystem path for a bundled asset.

    Wheels installed by pip normally expose package data as real files, but
    `as_file` also keeps this working if a future installer serves resources
    from an archive.
    """
    ref = resources.files(_ASSETS_PACKAGE).joinpath(*parts)
    return _STACK.enter_context(resources.as_file(ref))


def read_text_resource(*parts: str) -> str:
    return resources.files(_ASSETS_PACKAGE).joinpath(*parts).read_text(encoding="utf-8")

