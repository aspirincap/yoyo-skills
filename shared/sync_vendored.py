#!/usr/bin/env python3
"""Sync or verify self-contained copies of shared gateway and media runtime files."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]
AI_SKILLS = (
    "product-creative-scraper",
    "open-tiktok-script",
    "script-to-storyboard-video",
    "product-to-ugc-video",
    "product-detail-page-pipeline",
)
VIDEO_SKILLS = ("script-to-storyboard-video", "product-to-ugc-video")
IMAGE_SKILLS = (*VIDEO_SKILLS, "product-detail-page-pipeline")


def mappings() -> list[tuple[Path, Path]]:
    pairs: list[tuple[Path, Path]] = []
    for skill in AI_SKILLS:
        pairs.extend(
            [
                (ROOT / "shared/ai-gateway/ai_gateway.py", ROOT / skill / "scripts/ai_gateway.py"),
                (
                    ROOT / "shared/ai-gateway/configure_ai_gateway.py",
                    ROOT / skill / "scripts/configure_ai_gateway.py",
                ),
            ]
        )
    for skill in IMAGE_SKILLS:
        pairs.append((ROOT / "shared/media-runtime/image_tool.py", ROOT / skill / "scripts/image_tool.py"))
    for skill in VIDEO_SKILLS:
        pairs.append((ROOT / "shared/media-runtime/generate_video.py", ROOT / skill / "scripts/generate_video.py"))
    return pairs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    stale: list[str] = []
    for source, target in mappings():
        if args.check:
            if not target.exists() or source.read_bytes() != target.read_bytes():
                stale.append(str(target.relative_to(ROOT)))
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            target.chmod(source.stat().st_mode)
    if stale:
        print("Vendored files are stale:")
        for item in stale:
            print(f"- {item}")
        return 1
    print("Vendored files are synchronized." if args.check else "Vendored files updated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
