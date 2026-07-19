#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "shared" / "ai-gateway" / "ai_gateway.py"
CONFIGURE = ROOT / "shared" / "ai-gateway" / "configure_ai_gateway.py"


def load_module():
    spec = importlib.util.spec_from_file_location("ai_gateway_test", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    gateway = load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        global_config = root / "global.env"
        global_config.write_text(
            "AI_GATEWAY_BASE_URL=https://global.example\n"
            "AI_GATEWAY_API_KEY=global-secret\n"
            "AI_IMAGE_MODEL=global-image\n",
            encoding="utf-8",
        )
        skill_dir = root / "skill"
        skill_dir.mkdir()
        (skill_dir / ".env").write_text(
            "AI_GATEWAY_BASE_URL=https://skill.example\nAI_IMAGE_MODEL=skill-image\n",
            encoding="utf-8",
        )
        environment = {
            "AI_GATEWAY_CONFIG_FILE": str(global_config),
            "AI_GATEWAY_BASE_URL": "https://shell.example",
        }
        with mock.patch.dict(os.environ, environment, clear=True):
            assert gateway.gateway_base_url(skill_dir=skill_dir) == "https://shell.example"
            assert gateway.gateway_model("image", skill_dir=skill_dir) == "skill-image"
            assert gateway.gateway_api_key(skill_dir=skill_dir) == "global-secret"

        run_env = dict(os.environ)
        run_env["AI_GATEWAY_API_KEY"] = "test-secret"
        command = [
            sys.executable,
            str(CONFIGURE),
            "--config-file",
            str(root / "would-write.env"),
            "--base-url",
            "http://gateway.example",
            "--text-model",
            "text-model",
            "--vision-model",
            "vision-model",
            "--image-model",
            "image-model",
            "--image-sizes",
            "1024x1024,1024x1536",
            "--video-model",
            "video-model",
        ]
        result = subprocess.run(
            [*command, "--dry-run"],
            env=run_env,
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert "test-secret" not in result.stdout + result.stderr
        assert not (root / "would-write.env").exists()

        written = subprocess.run(
            command,
            env=run_env,
            text=True,
            capture_output=True,
            check=False,
        )
        assert written.returncode == 0, written.stderr
        assert "test-secret" not in written.stdout + written.stderr
        output = root / "would-write.env"
        assert output.exists()
        assert output.stat().st_mode & 0o777 == 0o600
        assert gateway.parse_env_file(output)["AI_GATEWAY_BASE_URL"] == "http://gateway.example"
        assert gateway.parse_env_file(output)["AI_IMAGE_SUPPORTED_SIZES"] == "1024x1024,1024x1536"

    sync = subprocess.run(
        [sys.executable, str(ROOT / "shared" / "sync_vendored.py"), "--check"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert sync.returncode == 0, sync.stdout + sync.stderr
    print("AI gateway tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
