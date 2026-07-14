#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "product_to_ugc.py"

def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        image = pathlib.Path(tmp) / "product.jpg"
        image.write_bytes(b"offline-placeholder")
        result = subprocess.run([
            sys.executable, str(SCRIPT), "--product-image", str(image),
            "--description", "Reusable insulated cup with a visible lid",
            "--heuristic-plan", "--dry-run", "--skip-merge",
            "--output-root", str(pathlib.Path(tmp) / "out"),
        ], text=True, capture_output=True, check=False)
        assert result.returncode == 0, result.stderr
        project_files = list((pathlib.Path(tmp) / "out").rglob("project.json"))
        assert project_files, "project.json was not created"
        prompt_text = "\n".join(p.read_text(errors="ignore") for p in (pathlib.Path(tmp) / "out").rglob("*.txt"))
        assert "female" not in prompt_text.lower()
    print("smoke tests passed")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
