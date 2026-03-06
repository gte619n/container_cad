"""File-based config storage for cadbox web UI.

Saves and loads container configurations as JSON files in ~/.cadbox/configs/.
"""

from __future__ import annotations

import json
from pathlib import Path

_STORAGE_DIR = Path.home() / ".cadbox" / "configs"


def _sanitize_name(name: str) -> str:
    """Replace path separators and other unsafe chars so names stay flat."""
    return name.replace("/", "_").replace("\\", "_").replace("\0", "_")


def _ensure_dir() -> Path:
    _STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    return _STORAGE_DIR


def list_configs() -> list[dict]:
    """Return a list of {name, modified} dicts for all saved configs."""
    d = _ensure_dir()
    configs = []
    for f in sorted(d.glob("*.json")):
        configs.append({
            "name": f.stem,
            "modified": f.stat().st_mtime,
        })
    return configs


def load_config(name: str) -> dict:
    """Load a saved config by name. Raises FileNotFoundError if missing."""
    path = _ensure_dir() / f"{_sanitize_name(name)}.json"
    if not path.exists():
        raise FileNotFoundError(f"Config '{name}' not found")
    return json.loads(path.read_text(encoding="utf-8"))


def save_config(name: str, data: dict) -> None:
    """Save a config dict under the given name."""
    path = _ensure_dir() / f"{_sanitize_name(name)}.json"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def delete_config(name: str) -> None:
    """Delete a saved config. Raises FileNotFoundError if missing."""
    path = _ensure_dir() / f"{_sanitize_name(name)}.json"
    if not path.exists():
        raise FileNotFoundError(f"Config '{name}' not found")
    path.unlink()
