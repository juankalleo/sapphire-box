"""Access to files bundled inside the installed package."""
from __future__ import annotations

import shutil
import tempfile
from contextlib import ExitStack
from importlib import resources
from pathlib import Path

_STACK = ExitStack()
_ASSETS_PACKAGE = "sapphirebox.assets"
_MATERIALIZED_ROOT = Path(tempfile.gettempdir()) / "sapphirebox-assets"


def _copy_resource_tree(ref, target: Path) -> None:
    if ref.is_dir():
        target.mkdir(parents=True, exist_ok=True)
        for child in ref.iterdir():
            _copy_resource_tree(child, target / child.name)
        return

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(ref.read_bytes())


def resource_path(*parts: str) -> Path:
    """Return a real filesystem path for a bundled asset.

    Wheels installed by pip normally expose package data as real files, but
    `as_file` also keeps this working if a future installer serves resources
    from an archive.
    """
    ref = resources.files(_ASSETS_PACKAGE).joinpath(*parts)
    if isinstance(ref, Path):
        return ref
    if ref.is_dir():
        target = _MATERIALIZED_ROOT.joinpath(*parts)
        if target.exists():
            shutil.rmtree(target)
        _copy_resource_tree(ref, target)
        return target
    return _STACK.enter_context(resources.as_file(ref))


def read_text_resource(*parts: str) -> str:
    return resources.files(_ASSETS_PACKAGE).joinpath(*parts).read_text(encoding="utf-8")
