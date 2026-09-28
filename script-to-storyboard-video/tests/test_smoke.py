#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "script_to_storyboard_video.py"

def load_pipeline():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("pipeline", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def main() -> int:
    pipeline = load_pipeline()
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert "name: script-to-storyboard-video" in skill
    assert "Do not use for creator-persona" in skill
    assert pipeline.split_segments(30, 15) == [(0, 15), (15, 30)]
    assert pipeline.split_segments(16, 15) == [(0, 8), (8, 16)]
    with tempfile.TemporaryDirectory() as tmp:
        image = pathlib.Path(tmp) / "product.png"
        image.write_bytes(b"dry-run-placeholder")
        result = subprocess.run([
            sys.executable, str(SCRIPT), "storyboard",
            "--script", "Hook, demonstration, CTA",
            "--product-image", str(image), "--duration", "16",
            "--output-root", str(pathlib.Path(tmp) / "out"), "--dry-run",
        ], text=True, capture_output=True, check=False)
        assert result.returncode == 0, result.stderr
        assert "--dry-run" in result.stdout
        unconfirmed = subprocess.run([
            sys.executable, str(SCRIPT), "video", "--project-dir", tmp,
        ], text=True, capture_output=True, check=False)
        assert unconfirmed.returncode != 0
        assert "before approval" in unconfirmed.stderr
    print("smoke tests passed")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
