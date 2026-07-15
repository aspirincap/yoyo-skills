#!/usr/bin/env python3
"""Configure a provider-neutral NewAPI-compatible gateway once for all skills."""

from __future__ import annotations

import argparse
import getpass
import os
from pathlib import Path
import tempfile

from ai_gateway import DEFAULT_CONFIG_FILE, parse_env_file


FIELDS = (
    "AI_GATEWAY_BASE_URL",
    "AI_GATEWAY_API_KEY",
    "AI_TEXT_MODEL",
    "AI_VISION_MODEL",
    "AI_IMAGE_MODEL",
    "AI_VIDEO_MODEL",
)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Configure one NewAPI-compatible gateway for supported AI skills.")
    p.add_argument("--config-file", type=Path, default=DEFAULT_CONFIG_FILE)
    p.add_argument("--base-url")
    p.add_argument("--text-model")
    p.add_argument("--vision-model")
    p.add_argument("--image-model")
    p.add_argument("--video-model")
    p.add_argument("--check", action="store_true", help="Show sanitized configuration status.")
    p.add_argument("--dry-run", action="store_true", help="Validate inputs without writing the token or file.")
    return p


def sanitized_status(path: Path) -> int:
    values = parse_env_file(path)
    print(f"Config: {path.expanduser()}")
    for key in FIELDS:
        value = os.getenv(key) or values.get(key)
        if key == "AI_GATEWAY_API_KEY":
            print(f"{key}=<CONFIGURED>" if value else f"{key}=<MISSING>")
        else:
            print(f"{key}={value or '<MISSING>'}")
    return 0 if (os.getenv("AI_GATEWAY_BASE_URL") or values.get("AI_GATEWAY_BASE_URL")) and (
        os.getenv("AI_GATEWAY_API_KEY") or values.get("AI_GATEWAY_API_KEY")
    ) else 1


def prompt(label: str, current: str = "", secret: bool = False) -> str:
    suffix = f" [{current}]" if current and not secret else ""
    reader = getpass.getpass if secret else input
    value = reader(f"{label}{suffix}: ").strip()
    return value or current


def main() -> int:
    args = parser().parse_args()
    path = args.config_file.expanduser()
    if args.check:
        return sanitized_status(path)

    existing = parse_env_file(path)
    base_url = args.base_url or prompt("Gateway base URL", existing.get("AI_GATEWAY_BASE_URL", ""))
    api_key = os.getenv("AI_GATEWAY_API_KEY") or prompt(
        "Gateway API key (input hidden)", existing.get("AI_GATEWAY_API_KEY", ""), secret=True
    )
    models = {
        "AI_TEXT_MODEL": args.text_model or prompt("Text model", existing.get("AI_TEXT_MODEL", "")),
        "AI_VISION_MODEL": args.vision_model or prompt("Vision model", existing.get("AI_VISION_MODEL", "")),
        "AI_IMAGE_MODEL": args.image_model or prompt("Image model", existing.get("AI_IMAGE_MODEL", "")),
        "AI_VIDEO_MODEL": args.video_model or prompt("Video model", existing.get("AI_VIDEO_MODEL", "")),
    }
    if not base_url or not api_key:
        raise SystemExit("Gateway base URL and API key are required.")
    if args.dry_run:
        print(f"Would configure: {path}")
        print("Gateway API key: <CONFIGURED>")
        return 0

    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"AI_GATEWAY_BASE_URL={base_url.rstrip('/')}",
        f"AI_GATEWAY_API_KEY={api_key}",
        *(f"{key}={value}" for key, value in models.items() if value),
        "",
    ]
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write("\n".join(lines))
        temp_path = Path(handle.name)
    temp_path.chmod(0o600)
    temp_path.replace(path)
    print(f"Configured: {path}")
    print("Gateway API key: <CONFIGURED>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
