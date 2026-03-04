"""JSON config loader for cadbox.

Provides :func:`load_config` and :func:`load_config_from_string` which parse
a JSON document into a validated :class:`~cadbox.models.ContainerConfig`.

All I/O and schema errors are surfaced as :class:`ConfigError` with
human-readable messages.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from cadbox.models import ContainerConfig


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------


class ConfigError(Exception):
    """Raised when a config file cannot be loaded or fails validation."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_config(path: str | Path) -> ContainerConfig:
    """Load and validate a :class:`ContainerConfig` from a JSON file.

    Args:
        path: Filesystem path to the ``.json`` config file.

    Returns:
        A fully validated :class:`ContainerConfig` instance.

    Raises:
        ConfigError: If the file is missing, contains invalid JSON, or fails
            Pydantic schema validation.
    """
    path = Path(path)

    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ConfigError(f"Config file not found: {path}") from None

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid JSON in {path}: {exc}") from exc

    return _parse(data)


def load_config_from_string(json_str: str) -> ContainerConfig:
    """Load and validate a :class:`ContainerConfig` from a JSON string.

    Useful for testing and reading configs piped via stdin.

    Args:
        json_str: A JSON-encoded string representing a :class:`ContainerConfig`.

    Returns:
        A fully validated :class:`ContainerConfig` instance.

    Raises:
        ConfigError: If the string contains invalid JSON or fails Pydantic
            schema validation.
    """
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid JSON: {exc}") from exc

    return _parse(data)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse(data: object) -> ContainerConfig:
    """Construct and validate a ContainerConfig from a parsed JSON object.

    Args:
        data: The already-decoded Python object (dict expected).

    Returns:
        A validated :class:`ContainerConfig`.

    Raises:
        ConfigError: On Pydantic validation failure.
    """
    try:
        return ContainerConfig.model_validate(data)
    except ValidationError as exc:
        # Format each error as  "field_path: message"
        lines = []
        for err in exc.errors():
            loc = " -> ".join(str(part) for part in err["loc"]) if err["loc"] else "(root)"
            lines.append(f"  {loc}: {err['msg']}")
        detail = "\n".join(lines)
        raise ConfigError(f"Config validation error:\n{detail}") from exc
