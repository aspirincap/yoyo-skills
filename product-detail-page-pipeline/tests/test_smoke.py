#!/usr/bin/env python3
from __future__ import annotations

import json
import hashlib
import pathlib
import subprocess
import sys
import tempfile

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import image_tool as image_tool_module
from aicreative_mcp import https_url, MCPError


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main() -> int:
    try:
        image_tool_module.safe_extra('{"prompt":"UNREVIEWED"}')
        raise AssertionError("protected --extra field was accepted")
    except SystemExit as exc:
        assert "cannot override core request fields" in str(exc)
    try:
        https_url("file:///etc/hosts")
        raise AssertionError("non-HTTPS image URL was accepted")
    except MCPError as exc:
        assert "must use HTTPS" in str(exc)

    ratio = subprocess.run([
        sys.executable, str(ROOT / "scripts" / "aspect_ratio_plan.py"),
        "--target-ratio", "1:5", "--supported-ratios", "1:1,4:5,3:4,2:3,9:16",
    ], text=True, capture_output=True, check=False)
    assert ratio.returncode == 0, ratio.stderr
    plan = json.loads(ratio.stdout)
    assert plan["operation"] == "decompose_into_vertical_modules"
    assert plan["split_and_stitch"] is False
    assert plan["segment_count"] >= 2
    assert plan["overlap_fraction"] == 0.0
    assert "one complete product-detail module" in plan["prompt_instruction"]

    gateway_check = subprocess.run([
        sys.executable, str(ROOT / "scripts" / "check_image_backend.py"),
        "--base-url", "https://mcp.invalid/api/mcp",
        "--model", "2102", "--operation", "generate",
        "--size", "1024x1536", "--offline",
    ], text=True, capture_output=True, check=False)
    assert gateway_check.returncode == 0, gateway_check.stderr
    gateway_status = json.loads(gateway_check.stdout)
    assert gateway_status["ok"] is True
    assert gateway_status["offline"] is True

    unsupported = subprocess.run([
        sys.executable, str(ROOT / "scripts" / "check_image_backend.py"),
        "--base-url", "https://mcp.invalid/api/mcp",
        "--model", "2102", "--size", "1024x1408", "--offline",
    ], text=True, capture_output=True, check=False)
    assert unsupported.returncode == 1
    assert "Unsupported requested size" in unsupported.stdout

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = pathlib.Path(tmp)
        text_to_render = {
            "language": "English",
            "verbatim": True,
            "kicker": "BUILT FOR THE CAR",
            "headline": "Simple proof",
            "subheadline": "Visible detail",
            "badges": ["CORDLESS"],
            "placement": "upper-left safe area",
            "typography": "bold modern sans serif",
            "max_lines": {"headline": 2, "subheadline": 2},
        }
        pack = {
            "platform_constraints": "Mobile-safe",
            "screens": [{
                "screen_id": 1,
                "role": "hero",
                "final_prompt_en": "Clean product hero image",
                "negative_prompt": "distortion",
                "text_to_render": text_to_render,
                "backend_params": {"aspect_ratio": "4:5", "reference_images": []},
                "assembly_plan": {"order": 2, "crop_after_generation": True}
            }, {
                "screen_id": 2,
                "role": "proof",
                "final_prompt_en": "Macro product proof image",
                "negative_prompt": "distortion",
                "text_to_render": {**text_to_render, "headline": "See the detail"},
                "backend_params": {"aspect_ratio": "4:5", "reference_images": []},
                "assembly_plan": {"order": 1, "crop_after_generation": True}
            }]
        }
        pack_path = tmp_path / "prompt_pack.json"
        pack_path.write_text(json.dumps(pack), encoding="utf-8")

        review_dir = tmp_path / "review"
        review_run = subprocess.run([
            sys.executable, str(ROOT / "scripts" / "prepare_generation_review.py"),
            "--prompt-pack", str(pack_path), "--output-dir", str(review_dir),
        ], text=True, capture_output=True, check=False)
        assert review_run.returncode == 0, review_run.stderr
        review = json.loads((review_dir / "generation_review.json").read_text())
        review_md = (review_dir / "generation_review.md").read_text()
        assert review["status"] == "awaiting_user_confirmation"
        assert review["generation_started"] is False
        assert review["page_count"] == 2
        assert "Page 1 · Screen 2" in review_md
        assert "Page 2 · Screen 1" in review_md
        assert "See the detail" in review_md
        assert "开始生图" in review_md

        no_approval = subprocess.run([
            sys.executable, str(ROOT / "scripts" / "run_image_generation.py"),
            "--prompt-pack", str(pack_path), "--output-dir", str(tmp_path / "blocked"),
            "--skip-backend-check",
        ], text=True, capture_output=True, check=False)
        assert no_approval.returncode != 0
        assert "explicitly confirms" in no_approval.stderr

        approval_path = review_dir / "generation_approval.json"
        vague_approval = subprocess.run([
            sys.executable, str(ROOT / "scripts" / "record_generation_approval.py"),
            "--prompt-pack", str(pack_path), "--review", str(review_dir / "generation_review.json"),
            "--output", str(approval_path), "--confirmation", "继续",
        ], text=True, capture_output=True, check=False)
        assert vague_approval.returncode != 0
        assert not approval_path.exists()
        for phrase in ("确认生活照图", "开始生产流程图"):
            false_positive = subprocess.run([
                sys.executable, str(ROOT / "scripts" / "record_generation_approval.py"),
                "--prompt-pack", str(pack_path), "--review", str(review_dir / "generation_review.json"),
                "--output", str(review_dir / f"invalid_{len(phrase)}.json"), "--confirmation", phrase,
            ], text=True, capture_output=True, check=False)
            assert false_positive.returncode != 0

        approval_run = subprocess.run([
            sys.executable, str(ROOT / "scripts" / "record_generation_approval.py"),
            "--prompt-pack", str(pack_path), "--review", str(review_dir / "generation_review.json"),
            "--output", str(approval_path), "--confirmation", "开始生图",
        ], text=True, capture_output=True, check=False)
        assert approval_run.returncode == 0, approval_run.stderr
        approval = json.loads(approval_path.read_text())
        assert approval["approved"] is True
        assert approval["prompt_pack_sha256"] == review["prompt_pack_sha256"]

        original_review_text = (review_dir / "generation_review.json").read_text()
        incomplete_review_path = review_dir / "incomplete_review.json"
        incomplete_review = {**review, "pages": review["pages"][:1], "page_count": 1}
        incomplete_review_path.write_text(json.dumps(incomplete_review), encoding="utf-8")
        incomplete_approval = subprocess.run([
            sys.executable, str(ROOT / "scripts" / "record_generation_approval.py"),
            "--prompt-pack", str(pack_path), "--review", str(incomplete_review_path),
            "--output", str(review_dir / "incomplete_approval.json"), "--confirmation", "开始生图",
        ], text=True, capture_output=True, check=False)
        assert incomplete_approval.returncode != 0
        assert "does not cover every" in incomplete_approval.stderr

        tampered_review_path = review_dir / "tampered_review.json"
        tampered_review = json.loads(json.dumps(review))
        tampered_review["pages"][0]["customer_copy"]["headline"] = "Different reviewed copy"
        tampered_review_path.write_text(json.dumps(tampered_review), encoding="utf-8")
        tampered_approval = subprocess.run([
            sys.executable, str(ROOT / "scripts" / "record_generation_approval.py"),
            "--prompt-pack", str(pack_path), "--review", str(tampered_review_path),
            "--output", str(review_dir / "tampered_approval.json"), "--confirmation", "开始生图",
        ], text=True, capture_output=True, check=False)
        assert tampered_approval.returncode != 0
        assert "does not cover every" in tampered_approval.stderr

        (review_dir / "generation_review.json").write_text(original_review_text + "\n", encoding="utf-8")
        changed_review = subprocess.run([
            sys.executable, str(ROOT / "scripts" / "run_image_generation.py"),
            "--prompt-pack", str(pack_path), "--output-dir", str(tmp_path / "changed-review"),
            "--approval-file", str(approval_path), "--skip-backend-check",
        ], text=True, capture_output=True, check=False)
        assert changed_review.returncode != 0
        assert "reviewed page summary" in changed_review.stderr
        (review_dir / "generation_review.json").write_text(original_review_text, encoding="utf-8")

        original_pack_text = pack_path.read_text()
        changed_pack = {**pack, "platform_constraints": "Changed after approval"}
        pack_path.write_text(json.dumps(changed_pack), encoding="utf-8")
        stale = subprocess.run([
            sys.executable, str(ROOT / "scripts" / "run_image_generation.py"),
            "--prompt-pack", str(pack_path), "--output-dir", str(tmp_path / "stale"),
            "--approval-file", str(approval_path), "--skip-backend-check",
        ], text=True, capture_output=True, check=False)
        assert stale.returncode != 0
        assert "Approval is stale" in stale.stderr
        pack_path.write_text(original_pack_text, encoding="utf-8")

        scoped_approval_path = review_dir / "scoped_approval.json"
        scoped_approval = subprocess.run([
            sys.executable, str(ROOT / "scripts" / "record_generation_approval.py"),
            "--prompt-pack", str(pack_path), "--review", str(review_dir / "generation_review.json"),
            "--output", str(scoped_approval_path), "--confirmation", "开始生1图",
            "--only-screen", "1",
        ], text=True, capture_output=True, check=False)
        assert scoped_approval.returncode == 0, scoped_approval.stderr
        scoped_data = json.loads(scoped_approval_path.read_text())
        assert scoped_data["approval_scope"] == "selected_pages"
        assert scoped_data["approved_screen_ids"] == ["1"]
        fake_image_tool = tmp_path / "fake_image_tool.py"
        fake_image_tool.write_text(
            "#!/usr/bin/env python3\n"
            "import pathlib, sys\n"
            "from PIL import Image\n"
            "output = pathlib.Path(sys.argv[sys.argv.index('--output') + 1])\n"
            "output.parent.mkdir(parents=True, exist_ok=True)\n"
            "Image.new('RGB', (8, 8), 'green').save(output)\n",
            encoding="utf-8",
        )
        scoped_run = subprocess.run([
            sys.executable, str(ROOT / "scripts" / "run_image_generation.py"),
            "--prompt-pack", str(pack_path), "--output-dir", str(tmp_path / "scoped-run"),
            "--approval-file", str(scoped_approval_path), "--only-screen", "1",
            "--skip-backend-check", "--image-tool", str(fake_image_tool),
        ], text=True, capture_output=True, check=False)
        assert scoped_run.returncode == 0, scoped_run.stderr
        scoped_manifest = json.loads((tmp_path / "scoped-run" / "generation_manifest.json").read_text())
        assert scoped_manifest["user_approval"]["approval_scope"] == "selected_pages"
        assert len(scoped_manifest["screens"]) == 1
        assert scoped_manifest["screens"][0]["artifact_validation"]["ok"] is True
        outside_scope = subprocess.run([
            sys.executable, str(ROOT / "scripts" / "run_image_generation.py"),
            "--prompt-pack", str(pack_path), "--output-dir", str(tmp_path / "outside-scope"),
            "--approval-file", str(scoped_approval_path), "--only-screen", "2",
            "--skip-backend-check", "--image-tool", str(fake_image_tool),
        ], text=True, capture_output=True, check=False)
        assert outside_scope.returncode != 0
        assert "outside the approval scope" in outside_scope.stderr

        extra_override = subprocess.run([
            sys.executable, str(ROOT / "scripts" / "run_image_generation.py"),
            "--prompt-pack", str(pack_path), "--output-dir", str(tmp_path / "extra-override"),
            "--extra", '{"prompt":"UNREVIEWED","model":"other"}', "--dry-run",
        ], text=True, capture_output=True, check=False)
        assert extra_override.returncode != 0
        assert "cannot override reviewed request fields" in extra_override.stderr

        empty_tool = tmp_path / "empty_image_tool.py"
        empty_tool.write_text("#!/usr/bin/env python3\nraise SystemExit(0)\n", encoding="utf-8")
        empty_run = subprocess.run([
            sys.executable, str(ROOT / "scripts" / "run_image_generation.py"),
            "--prompt-pack", str(pack_path), "--output-dir", str(tmp_path / "empty-run"),
            "--approval-file", str(scoped_approval_path), "--only-screen", "1",
            "--skip-backend-check", "--image-tool", str(empty_tool),
        ], text=True, capture_output=True, check=False)
        assert empty_run.returncode != 0
        empty_manifest = json.loads((tmp_path / "empty-run" / "generation_manifest.json").read_text())
        assert empty_manifest["screens"][0]["artifact_validation"]["ok"] is False

        unknown_screen = subprocess.run([
            sys.executable, str(ROOT / "scripts" / "run_image_generation.py"),
            "--prompt-pack", str(pack_path), "--output-dir", str(tmp_path / "unknown-screen"),
            "--only-screen", "999", "--dry-run",
        ], text=True, capture_output=True, check=False)
        assert unknown_screen.returncode != 0
        assert "not present in the prompt pack" in unknown_screen.stderr

        duplicate_pack = {**pack, "screens": [pack["screens"][0], {**pack["screens"][1], "screen_id": "01"}]}
        duplicate_pack_path = tmp_path / "duplicate_pack.json"
        duplicate_pack_path.write_text(json.dumps(duplicate_pack), encoding="utf-8")
        duplicate_review = subprocess.run([
            sys.executable, str(ROOT / "scripts" / "prepare_generation_review.py"),
            "--prompt-pack", str(duplicate_pack_path), "--output-dir", str(tmp_path / "duplicate-review"),
        ], text=True, capture_output=True, check=False)
        assert duplicate_review.returncode != 0
        assert "Duplicate screen_id" in duplicate_review.stderr

        missing_pack = json.loads(json.dumps(pack))
        missing_pack["screens"][0]["backend_params"]["reference_images"] = ["/etc/hosts"]
        missing_pack_path = tmp_path / "missing_reference_pack.json"
        missing_pack_path.write_text(json.dumps(missing_pack), encoding="utf-8")
        missing_review_dir = tmp_path / "missing-review"
        missing_review_run = subprocess.run([
            sys.executable, str(ROOT / "scripts" / "prepare_generation_review.py"),
            "--prompt-pack", str(missing_pack_path), "--output-dir", str(missing_review_dir),
        ], text=True, capture_output=True, check=False)
        assert missing_review_run.returncode == 0, missing_review_run.stderr
        missing_approval_path = missing_review_dir / "generation_approval.json"
        missing_approval = subprocess.run([
            sys.executable, str(ROOT / "scripts" / "record_generation_approval.py"),
            "--prompt-pack", str(missing_pack_path),
            "--review", str(missing_review_dir / "generation_review.json"),
            "--output", str(missing_approval_path), "--confirmation", "开始生图",
        ], text=True, capture_output=True, check=False)
        assert missing_approval.returncode == 0, missing_approval.stderr
        missing_run = subprocess.run([
            sys.executable, str(ROOT / "scripts" / "run_image_generation.py"),
            "--prompt-pack", str(missing_pack_path), "--output-dir", str(tmp_path / "missing-run"),
            "--approval-file", str(missing_approval_path), "--skip-backend-check",
            "--image-tool", str(fake_image_tool),
        ], text=True, capture_output=True, check=False)
        assert missing_run.returncode != 0
        assert "declared reference images are missing" in missing_run.stderr
        assert "absolute paths require an explicit --reference-dir" in missing_run.stderr

        output = tmp_path / "generated"
        dry = subprocess.run([
            sys.executable, str(ROOT / "scripts" / "run_image_generation.py"),
            "--prompt-pack", str(pack_path), "--output-dir", str(output), "--dry-run",
        ], text=True, capture_output=True, check=False)
        assert dry.returncode == 0, dry.stderr
        manifest = json.loads((output / "generation_manifest.json").read_text())
        assert manifest["dry_run"] is True
        assert manifest["user_approval"]["required_for_real_generation"] is True
        assert manifest["screens"][0]["executed"] is False
        assert manifest["backend_preflight"]["skipped"] is True
        assert manifest["screens"][0]["artifact_role"] == "final_original_screen"
        assert len(manifest["deliverables"]["original_screens"]) == 2
        prompt = (output / "prompts" / "screen_01.txt").read_text()
        assert 'headline: "Simple proof"' in prompt
        assert 'subheadline: "Visible detail"' in prompt
        assert 'badge_1: "CORDLESS"' in prompt
        assert "directly and visibly inside this image" in prompt
        assert "Do not translate" in prompt
        assert "Post-production" not in prompt
        assert "Final delivery aspect ratio: 4:5" in prompt
        assert "central 83% of canvas height" in prompt
        command = manifest["screens"][0]["command"]
        assert str(ROOT / "scripts" / "image_tool.py") in command
        assert command[command.index("--size") + 1] == "1024x1536"

        tool_output = tmp_path / "image-tool-dry-run"
        tool_dry = subprocess.run([
            sys.executable, str(ROOT / "scripts" / "run_image_generation.py"),
            "--prompt-pack", str(pack_path), "--output-dir", str(tool_output),
            "--image-tool-dry-run", "--model", "2102",
            "--base-url", "https://mcp.invalid/api/mcp",
        ], text=True, capture_output=True, check=False)
        assert tool_dry.returncode == 0, tool_dry.stderr
        tool_manifest = json.loads((tool_output / "generation_manifest.json").read_text())
        assert tool_manifest["screens"][0]["executed"] is True
        assert tool_manifest["backend_preflight"]["skipped"] is True

        image_dir = tmp_path / "originals"
        image_dir.mkdir()
        screen_1 = image_dir / "screen_01.png"
        screen_2 = image_dir / "screen_02.png"
        Image.new("RGB", (64, 96), "red").save(screen_1)
        Image.new("RGB", (64, 96), "blue").save(screen_2)
        before = {screen_1: sha256(screen_1), screen_2: sha256(screen_2)}
        assembled = tmp_path / "assembled"
        assembly = subprocess.run([
            sys.executable, str(ROOT / "scripts" / "assemble_detail_page.py"),
            "--prompt-pack", str(pack_path), "--image-dir", str(image_dir),
            "--output-dir", str(assembled),
        ], text=True, capture_output=True, check=False)
        assert assembly.returncode == 0, assembly.stderr
        assert all(sha256(path) == digest for path, digest in before.items())
        assert (assembled / "contact_sheet.png").exists()
        assert (assembled / "detail_page_long.png").exists()
        with Image.open(assembled / "detail_page_long.png") as long_page:
            assert long_page.size == (64, 160)
            assert long_page.getpixel((0, 0)) == (0, 0, 255)  # order 1: screen 02
            assert long_page.getpixel((0, 159)) == (255, 0, 0)  # order 2: screen 01
        assembly_manifest = json.loads((assembled / "assembly_manifest.json").read_text())
        assert assembly_manifest["originals_preserved"] is True
        assert [item["screen_id"] for item in assembly_manifest["original_screens"]] == [2, 1]
        assert [item["sha256"] for item in assembly_manifest["original_screens"]] == [before[screen_2], before[screen_1]]
        assert all(item["assembly_transform"]["operation"] == "center_crop_derivative" for item in assembly_manifest["original_screens"])
        assert len(assembly_manifest["derivatives"]) == 2

    assert not (ROOT / "scripts" / "apply_text_overlay.py").exists()
    assert (ROOT / "scripts" / "aicreative_mcp.py").exists()
    assert (ROOT / "scripts" / "image_tool.py").exists()
    assert (ROOT / "scripts" / "prepare_generation_review.py").exists()
    assert (ROOT / "scripts" / "record_generation_approval.py").exists()
    print("smoke tests passed")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
