"""Helpers for loading the user configuration file (~/.batuta/config.json)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

CONFIG_DIR = Path.home() / ".batuta"
CONFIG_FILE = CONFIG_DIR / "config.json"


@lru_cache(maxsize=1)
def load_config() -> dict[str, Any]:
    """Load configuration data from disk (cached)."""

    if not CONFIG_FILE.exists():
        return {}

    try:
        raw = CONFIG_FILE.read_text()
    except OSError:
        return {}

    try:
        data = json.loads(raw)
    except ValueError:
        return {}

    if isinstance(data, dict):
        return data

    return {}


def get_config_value(key: str, default: Any | None = None) -> Any | None:
    """Fetch a configuration value by key."""

    return load_config().get(key, default)


def reload_config() -> None:
    """Force the cached configuration to be reloaded on next access."""

    load_config.cache_clear()
