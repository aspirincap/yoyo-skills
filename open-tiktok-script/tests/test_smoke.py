#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_module(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    downloader = load_module("download_tiktok", ROOT / "scripts" / "download_tiktok.py")
    analyzer = load_module("analyze_video", ROOT / "scripts" / "analyze_video.py")

    urls = downloader.extract_tiktok_urls([
        "watch https://vm.tiktok.com/abc/ now",
        "https://www.tiktok.com/@creator/video/123",
        "https://www.tiktok.com/@creator/video/123",
    ])
    assert urls == ["https://vm.tiktok.com/abc/", "https://www.tiktok.com/@creator/video/123"]

    command = downloader.build_command(
        "https://www.tiktok.com/@creator/video/123",
        "/tmp/video.%(ext)s",
        None,
        "socks5://user:secret@127.0.0.1:7890",
    )
    assert "--no-check-certificates" not in command
    assert "--cookies-from-browser" not in command
    assert "--proxy" in command

    headers = analyzer.auth_headers("secret", "x-goog")
    assert headers["x-goog-api-key"] == "secret"
    assert "Authorization" not in headers
    assert analyzer.normalize_model("flash") == "gemini-2.5-flash"
    assert analyzer.is_placeholder_value("replace_with_your_key")
    assert analyzer.is_placeholder_value("placeholder")
    assert not analyzer.is_placeholder_value("configured-value")
    assert "AI_GATEWAY_API_KEY" in analyzer.API_KEY_ENV_VARS

    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    notice = (ROOT / "NOTICE.md").read_text(encoding="utf-8")
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    source_url = "https://github.com/alchaincyf/huashu-skills/tree/master/huashu-douyin-script"
    for text in (skill, readme, notice):
        assert source_url in text
    assert ".env" in gitignore
    assert "https://llm-api.mobvista.com" not in skill + readme
    assert "gemini-3.5-flash" not in skill + readme
    assert "configure_ai_gateway.py" in skill + readme

    for script in ("download_tiktok.py", "analyze_video.py"):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / script), "--help"],
            text=True, capture_output=True, check=False,
        )
        assert result.returncode == 0, result.stderr

    print("smoke tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
