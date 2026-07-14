"""Shared environment helpers for ad-storyboard-seedance scripts."""

from __future__ import annotations

import os
import pathlib
import shlex
from collections.abc import Iterable


ENV_FILE_ENV = "AD_STORYBOARD_SEEDANCE_ENV_FILE"
COMMON_BASE_URL_ENV = "AD_STORYBOARD_BASE_URL"
SKILL_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _parse_env_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    if stripped.startswith("export "):
        stripped = stripped[len("export ") :].strip()
    if "=" not in stripped:
        return None
    key, value = stripped.split("=", 1)
    key = key.strip()
    if not key:
        return None
    value = value.strip()
    try:
        parts = shlex.split(value, comments=False, posix=True)
        if len(parts) == 1:
            value = parts[0]
    except ValueError:
        value = value.strip("\"'")
    return key, value


def _load_env_file(path: pathlib.Path) -> bool:
    if not path.exists():
        return False
    for line in path.read_text(encoding="utf-8").splitlines():
        parsed = _parse_env_line(line)
        if not parsed:
            continue
        key, value = parsed
        os.environ.setdefault(key, value)
    return True


def load_skill_env() -> list[pathlib.Path]:
    """Load explicit and skill-local env files without overriding shell env."""
    candidates: list[pathlib.Path] = []
    explicit = os.getenv(ENV_FILE_ENV)
    if explicit:
        candidates.append(pathlib.Path(explicit).expanduser())
    candidates.append(SKILL_ROOT / ".env")

    loaded: list[pathlib.Path] = []
    seen: set[pathlib.Path] = set()
    for candidate in candidates:
        path = candidate.resolve()
        if path in seen:
            continue
        seen.add(path)
        if _load_env_file(path):
            loaded.append(path)
    return loaded


def env_first(names: Iterable[str]) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


def resolve_base_url(value: str | None, env_names: Iterable[str]) -> str:
    base_url = value or env_first(env_names)
    if base_url:
        return base_url
    joined = ", ".join(env_names)
    raise SystemExit(
        "Base URL is required. Set one of these env vars "
        f"({joined}) in the skill-local .env file, export it in your shell, "
        "or pass --base-url explicitly."
    )
