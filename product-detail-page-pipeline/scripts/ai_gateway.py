#!/usr/bin/env python3
"""Provider-neutral configuration loader for NewAPI-compatible AI gateways."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable


CONFIG_FILE_ENV = "AI_GATEWAY_CONFIG_FILE"
DEFAULT_CONFIG_FILE = Path.home() / ".config" / "ai-gateway" / "config.env"


def is_placeholder_value(value: str) -> bool:
    normalized = value.strip().lower()
    return (
        normalized in {
            "placeholder",
            "changeme",
            "your-key",
            "your_key",
            "model-id",
            "seedance-model-id",
        }
        or "replace_with" in normalized
        or ".example.com" in normalized
        or normalized.startswith("your-")
    )


def parse_env_file(path: Path) -> dict[str, str]:
    if not path.exists() or not path.is_file():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and value and not is_placeholder_value(value):
            values[key] = value
    return values


def global_config_file() -> Path:
    configured = os.getenv(CONFIG_FILE_ENV)
    return Path(configured).expanduser() if configured else DEFAULT_CONFIG_FILE


def _layers(skill_dir: Path | None) -> tuple[dict[str, str], ...]:
    environment = dict(os.environ)
    skill_values = parse_env_file(skill_dir / ".env") if skill_dir else {}
    global_values = parse_env_file(global_config_file())
    return environment, skill_values, global_values


def get_setting(
    primary: str,
    legacy: Iterable[str] = (),
    *,
    default: str | None = None,
    skill_dir: Path | None = None,
) -> str | None:
    """Resolve one value with env > skill .env > global config > default precedence."""
    names = (primary, *tuple(legacy))
    for layer in _layers(skill_dir):
        for name in names:
            value = layer.get(name)
            if value and not is_placeholder_value(value):
                return value
    return default


def get_first_setting(
    names: Iterable[str],
    *,
    skill_dir: Path | None = None,
) -> str | None:
    names = tuple(dict.fromkeys(names))
    if not names:
        return None
    return get_setting(names[0], names[1:], skill_dir=skill_dir)


def gateway_base_url(*legacy: str, skill_dir: Path | None = None) -> str | None:
    value = get_setting("AI_GATEWAY_BASE_URL", legacy, skill_dir=skill_dir)
    return value.rstrip("/") if value else None


def gateway_api_key(*legacy: str, skill_dir: Path | None = None) -> str | None:
    return get_setting("AI_GATEWAY_API_KEY", legacy, skill_dir=skill_dir)


def gateway_model(
    kind: str,
    *legacy: str,
    default: str | None = None,
    skill_dir: Path | None = None,
) -> str | None:
    key = f"AI_{kind.upper()}_MODEL"
    return get_setting(key, legacy, default=default, skill_dir=skill_dir)
