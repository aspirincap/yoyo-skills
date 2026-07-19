#!/usr/bin/env python3
"""Run an e-commerce prompt_pack.json through the local image_tool.py CLI."""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import pathlib
import re
import shlex
import subprocess
import sys
import time
from typing import Any

from ai_gateway import get_setting


SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
DEFAULT_IMAGE_TOOL = SCRIPT_DIR / "image_tool.py"
DEFAULT_SUPPORTED_SIZES = "1024x1024,1024x1536,1536x1024"
SUPPORTED_REFERENCE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
PROTECTED_EXTRA_FIELDS = {"model", "prompt", "messages", "modalities", "n", "size", "image", "mask"}
ALLOWED_EXTRA_FIELDS = {"seed"}


def read_json(path: pathlib.Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"Expected JSON object: {path}")
    return data


def write_json(path: pathlib.Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_text(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_approval(
    prompt_pack: pathlib.Path,
    approval_path: pathlib.Path | None,
    requested_screen_ids: set[str],
) -> dict[str, Any]:
    if approval_path is None:
        raise SystemExit(
            "Real image generation is blocked until the user reviews every page and explicitly confirms. "
            "Create an approval with record_generation_approval.py, then pass --approval-file."
        )
    approval = read_json(approval_path)
    if approval.get("approved") is not True:
        raise SystemExit(f"Approval file is not approved: {approval_path}")
    scope = approval.get("approval_scope")
    if scope not in {"all_pages_in_prompt_pack", "selected_pages"} or not approval.get("confirmation"):
        raise SystemExit("Approval file does not contain explicit generation approval.")
    try:
        approved_screen_ids = {
            screen_id({"screen_id": item}, index)
            for index, item in enumerate(approval.get("approved_screen_ids", []))
        }
    except ValueError as exc:
        raise SystemExit(f"Approval contains an invalid screen ID: {exc}") from exc
    if scope == "selected_pages":
        if not requested_screen_ids:
            raise SystemExit("This approval covers selected pages only. Pass matching --only-screen values.")
        unauthorized = sorted(requested_screen_ids - approved_screen_ids)
        if unauthorized:
            raise SystemExit("Requested screens are outside the approval scope: " + ", ".join(unauthorized))
    current_hash = sha256(prompt_pack)
    if approval.get("prompt_pack_sha256") != current_hash:
        raise SystemExit(
            "Approval is stale because prompt_pack.json changed after user confirmation. "
            "Export a new per-page review and ask the user to confirm again."
        )
    review_value = approval.get("review")
    review_path = pathlib.Path(review_value) if isinstance(review_value, str) and review_value else None
    if review_path is None or not review_path.is_file() or sha256(review_path) != approval.get("review_sha256"):
        raise SystemExit(
            "The reviewed page summary is missing or changed after approval. "
            "Export a new per-page review and ask the user to confirm again."
        )
    return {
        "approval_file": str(approval_path.resolve()),
        "approved": True,
        "approval_scope": approval.get("approval_scope"),
        "approved_screen_ids": sorted(approved_screen_ids),
        "approved_at": approval.get("approved_at"),
        "confirmation": approval.get("confirmation"),
        "prompt_pack_sha256": current_hash,
    }


def shell_join(cmd: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in cmd)


def infer_size(aspect_ratio: str, default_size: str) -> str:
    ratio = (aspect_ratio or "").strip()
    if ratio in {"9:16", "2:3"}:
        return "1024x1536"
    if ratio in {"16:9", "3:2"}:
        return "1536x1024"
    if ratio in {"4:5", "3:4", "8:11", "2000:2750", "1:4"}:
        return "1024x1536"
    if ratio in {"5:4", "4:3", "11:8"}:
        return "1536x1024"
    return default_size


def ratio_value(value: str) -> float | None:
    try:
        left, right = value.split(":", 1)
        width, height = float(left), float(right)
        return width / height if width > 0 and height > 0 else None
    except (TypeError, ValueError):
        return None


def crop_safe_instruction(screen: dict[str, Any], render_size: str) -> str | None:
    plan = screen.get("assembly_plan")
    if not isinstance(plan, dict) or not plan.get("crop_after_generation"):
        return None
    params = screen.get("backend_params")
    target_text = str(params.get("aspect_ratio") or "") if isinstance(params, dict) else ""
    target = ratio_value(target_text)
    try:
        width_text, height_text = render_size.lower().split("x", 1)
        canvas = float(width_text) / float(height_text)
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    if target is None or abs(target - canvas) / target <= 0.01:
        return None
    if target > canvas:
        fraction = canvas / target
        safe_area = f"central {fraction:.0%} of canvas height; top and bottom are crop-only extension"
    else:
        fraction = target / canvas
        safe_area = f"central {fraction:.0%} of canvas width; left and right are crop-only extension"
    return (
        f"Final delivery aspect ratio: {target_text}. The backend canvas is {render_size}. "
        f"Keep the complete product, every required word, and all evidence inside the {safe_area}. "
        "The assembler will crop only the derivative; do not place meaningful content in the extension area."
    )


def screen_id(screen: dict[str, Any], index: int) -> str:
    raw = screen.get("screen_id", index + 1)
    if isinstance(raw, bool):
        raise ValueError("screen_id must not be a boolean.")
    text = str(raw).strip()
    if not text:
        raise ValueError("screen_id must not be empty.")
    try:
        numeric = int(text)
    except (TypeError, ValueError):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", text):
            raise ValueError(
                f"Unsafe screen_id {raw!r}. Use a positive integer or letters, digits, hyphens and underscores."
            )
        return text
    if numeric <= 0:
        raise ValueError("Numeric screen_id values must be positive.")
    return f"{numeric:02d}"


def validate_screens(screens: list[Any]) -> list[dict[str, Any]]:
    validated: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, screen in enumerate(screens):
        if not isinstance(screen, dict):
            raise SystemExit(f"Screen entry {index + 1} must be a JSON object.")
        try:
            label = screen_id(screen, index)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        if label in seen:
            raise SystemExit(f"Duplicate screen_id resolves to screen_{label}: {screen.get('screen_id', index + 1)!r}")
        seen.add(label)
        validated.append(screen)
    return validated


def prompt_for_screen(pack: dict[str, Any], screen: dict[str, Any], render_size: str = "") -> str:
    final = (
        screen.get("final_prompt_en")
        or screen.get("final_prompt_localized")
        or screen.get("screen_specific_prompt")
        or ""
    )
    if not isinstance(final, str) or not final.strip():
        raise ValueError(f"Screen {screen.get('screen_id')} is missing final prompt text.")

    parts = [final.strip()]
    negative = screen.get("negative_prompt")
    if isinstance(negative, str) and negative.strip():
        parts.append(f"Negative prompt: {negative.strip()}")
    copy = screen.get("text_to_render")
    if not isinstance(copy, dict):
        raise ValueError(
            f"Screen {screen.get('screen_id')} is missing text_to_render. "
            "Every screen must state the customer-facing copy the image model renders directly."
        )
    if copy.get("verbatim") is False:
        raise ValueError(f"Screen {screen.get('screen_id')} must set text_to_render.verbatim to true.")

    text_fields: list[tuple[str, str]] = []
    for field in ("kicker", "headline", "subheadline"):
        value = copy.get(field)
        if isinstance(value, str) and value.strip():
            text_fields.append((field, value.strip()))
    badges = copy.get("badges")
    if badges is not None and not isinstance(badges, list):
        raise ValueError(f"Screen {screen.get('screen_id')} text_to_render.badges must be an array.")
    if isinstance(badges, list):
        for badge_index, badge in enumerate(badges, start=1):
            if isinstance(badge, str) and badge.strip():
                text_fields.append((f"badge_{badge_index}", badge.strip()))

    language = str(copy.get("language") or "as written")
    copy_lines = [
        "Render the following customer-facing copy directly and visibly inside this image.",
        "The image model itself must render the copy as part of the finished screen.",
        "Render only the non-empty strings listed below, exactly as quoted.",
        "Preserve spelling, capitalization, punctuation, and language exactly. Do not translate, "
        "paraphrase, autocorrect, omit, duplicate, or add customer-facing words.",
        f"Copy language: {language}.",
    ]
    if text_fields:
        copy_lines.extend(f"- {label}: {json.dumps(value, ensure_ascii=False)}" for label, value in text_fields)
    else:
        copy_lines.append("- No customer-facing words are required for this screen.")

    placement = copy.get("placement")
    if isinstance(placement, str) and placement.strip():
        copy_lines.append(f"Text placement: {placement.strip()}")
    typography = copy.get("typography")
    if isinstance(typography, str) and typography.strip():
        copy_lines.append(f"Typography direction: {typography.strip()}")
    max_lines = copy.get("max_lines")
    if isinstance(max_lines, dict):
        limits = []
        for field in ("kicker", "headline", "subheadline"):
            value = max_lines.get(field)
            if isinstance(value, int) and value > 0:
                limits.append(f"{field}={value}")
        if limits:
            copy_lines.append("Maximum line counts: " + ", ".join(limits) + ".")
    copy_lines.append("Keep every required string legible, uncropped, and inside the safe area.")
    parts.append("\n".join(copy_lines))
    crop_instruction = crop_safe_instruction(screen, render_size)
    if crop_instruction:
        parts.append(crop_instruction)
    platform = pack.get("platform_constraints")
    if isinstance(platform, str) and platform.strip() and platform.strip() not in final:
        parts.append(f"Platform constraints: {platform.strip()}")
    return "\n\n".join(parts).strip() + "\n"


def validate_extra(value: str | None) -> None:
    if not value:
        return
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"--extra must be valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise SystemExit("--extra must be a JSON object.")
    protected = sorted(PROTECTED_EXTRA_FIELDS.intersection(parsed))
    if protected:
        raise SystemExit(
            "--extra cannot override reviewed request fields: " + ", ".join(protected)
        )
    unsupported = sorted(set(parsed) - ALLOWED_EXTRA_FIELDS)
    if unsupported:
        raise SystemExit(
            "The approval-bound runner only allows the seed field in --extra; unsupported fields: "
            + ", ".join(unsupported)
        )


def contains_symlink(candidate: pathlib.Path, root: pathlib.Path) -> bool:
    try:
        relative = candidate.absolute().relative_to(root.absolute())
    except ValueError:
        return False
    current = root.absolute()
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            return True
    return False


def verify_reference_image(path: pathlib.Path) -> None:
    if path.suffix.lower() not in SUPPORTED_REFERENCE_EXTENSIONS:
        raise ValueError("unsupported image extension")
    mime_type = mimetypes.guess_type(path.name)[0]
    if not mime_type or not mime_type.startswith("image/"):
        raise ValueError("file does not have an image MIME type")
    try:
        from PIL import Image

        with Image.open(path) as image:
            image.verify()
    except Exception as exc:
        raise ValueError(f"file is not a decodable image: {exc}") from exc


def resolve_reference(
    path_value: str,
    roots: list[pathlib.Path],
    absolute_roots: list[pathlib.Path],
) -> pathlib.Path | None:
    raw = pathlib.Path(path_value).expanduser()
    if not raw.is_absolute() and ".." in raw.parts:
        raise ValueError("parent-directory traversal is not allowed")
    candidate_pairs: list[tuple[pathlib.Path, pathlib.Path]] = []
    if raw.is_absolute():
        candidate_pairs.extend((raw, root) for root in absolute_roots)
        if not candidate_pairs:
            raise ValueError("absolute paths require an explicit --reference-dir authorization root")
    else:
        for root in roots:
            candidate_pairs.append((root / raw, root))
            candidate_pairs.append((root / "images" / raw, root))
    invalid_reason: str | None = None
    for candidate, root in candidate_pairs:
        root_resolved = root.expanduser().resolve()
        if contains_symlink(candidate, root):
            invalid_reason = "symlinked references are not allowed"
            continue
        try:
            resolved = candidate.resolve(strict=True)
        except FileNotFoundError:
            continue
        try:
            resolved.relative_to(root_resolved)
        except ValueError:
            invalid_reason = "reference resolves outside its authorized root"
            continue
        if not resolved.is_file():
            continue
        try:
            verify_reference_image(resolved)
        except ValueError as exc:
            invalid_reason = str(exc)
            continue
        return resolved
    if invalid_reason:
        raise ValueError(invalid_reason)
    return None


def references_for_screen(
    screen: dict[str, Any],
    prompt_pack_path: pathlib.Path,
    reference_dirs: list[pathlib.Path],
) -> tuple[list[pathlib.Path], list[str]]:
    params = screen.get("backend_params")
    names: list[str] = []
    if isinstance(params, dict) and isinstance(params.get("reference_images"), list):
        names = [str(item) for item in params["reference_images"] if str(item).strip()]

    roots = [prompt_pack_path.parent.resolve(), *(root.expanduser().resolve() for root in reference_dirs)]
    absolute_roots = [root.expanduser().resolve() for root in reference_dirs]
    found: list[pathlib.Path] = []
    missing: list[str] = []
    for name in names:
        try:
            resolved = resolve_reference(name, roots, absolute_roots)
        except ValueError as exc:
            missing.append(f"{name} ({exc})")
            continue
        if resolved:
            found.append(resolved)
        else:
            missing.append(name)
    return found, missing


def inspect_output_image(path: pathlib.Path) -> dict[str, Any]:
    if not path.is_file():
        return {"ok": False, "error": "expected image file was not created"}
    if path.stat().st_size <= 0:
        return {"ok": False, "error": "expected image file is empty"}
    try:
        from PIL import Image

        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            width, height = image.size
            image_format = image.format
    except Exception as exc:
        return {"ok": False, "error": f"expected output is not a decodable image: {exc}"}
    return {
        "ok": True,
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
        "width": width,
        "height": height,
        "format": image_format,
    }


def run_command(cmd: list[str], dry_run: bool) -> dict[str, Any]:
    started = time.time()
    if dry_run:
        return {
            "executed": False,
            "returncode": 0,
            "duration_seconds": 0.0,
            "stdout": "",
            "stderr": "",
            "command": cmd,
        }
    proc = subprocess.run(cmd, text=True, capture_output=True)
    return {
        "executed": True,
        "returncode": proc.returncode,
        "duration_seconds": round(time.time() - started, 3),
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "command": cmd,
    }


def build_command(
    args: argparse.Namespace,
    mode: str,
    prompt_path: pathlib.Path,
    output_path: pathlib.Path,
    response_path: pathlib.Path,
    references: list[pathlib.Path],
    aspect_ratio: str,
) -> list[str]:
    cmd = [
        sys.executable,
        str(args.image_tool),
        mode,
        "--prompt-file",
        str(prompt_path),
        "--size",
        args.size or infer_size(aspect_ratio, args.default_size),
        "--output",
        str(output_path),
        "--save-json",
        str(response_path),
        "--timeout",
        str(args.timeout),
    ]
    if args.model:
        cmd.extend(["--model", args.model])
    if args.base_url:
        cmd.extend(["--base-url", args.base_url])
    if args.endpoint:
        cmd.extend(["--endpoint", args.endpoint])
    if args.output_format:
        cmd.extend(["--output-format", args.output_format])
    if args.quality:
        cmd.extend(["--quality", args.quality])
    if args.background:
        cmd.extend(["--background", args.background])
    if args.extra:
        cmd.extend(["--extra", args.extra])
    if args.image_tool_dry_run:
        cmd.append("--dry-run")
    if mode == "edit":
        for ref in references:
            cmd.extend(["--image", str(ref)])
    return cmd


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Batch-generate e-commerce detail images from prompt_pack.json.")
    parser.add_argument("--prompt-pack", required=True, type=pathlib.Path)
    parser.add_argument("--output-dir", required=True, type=pathlib.Path)
    configured_tool = os.getenv("IMAGE_TOOL_PATH") or str(DEFAULT_IMAGE_TOOL)
    parser.add_argument("--image-tool", type=pathlib.Path, default=pathlib.Path(configured_tool))
    parser.add_argument("--reference-dir", action="append", type=pathlib.Path, default=[])
    parser.add_argument("--model", default=os.getenv("AI_IMAGE_MODEL") or os.getenv("IMAGE_MODEL"))
    parser.add_argument("--base-url", default=os.getenv("AI_GATEWAY_BASE_URL"))
    parser.add_argument("--mode", choices=["auto", "generate", "edit"], default="auto")
    parser.add_argument("--endpoint", choices=["auto", "images", "chat"], default="auto")
    parser.add_argument("--size", help="Forwarded to image_tool.py. If omitted, inferred from aspect ratio.")
    parser.add_argument("--default-size", default="1024x1024")
    parser.add_argument("--output-format")
    parser.add_argument("--quality")
    parser.add_argument("--background")
    parser.add_argument("--extra", help="JSON object forwarded to image_tool.py --extra.")
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument(
        "--supported-sizes",
        default=get_setting(
            "AI_IMAGE_SUPPORTED_SIZES",
            default=DEFAULT_SUPPORTED_SIZES,
            skill_dir=SKILL_DIR,
        ),
        help="Comma-separated sizes supported by the selected image model.",
    )
    parser.add_argument("--skip-backend-check", action="store_true", help="Skip the automatic non-generating backend preflight.")
    parser.add_argument("--only-screen", action="append", help="Generate only these screen IDs.")
    parser.add_argument("--dry-run", action="store_true", help="Do not execute image_tool.py; only write prompts and manifest.")
    parser.add_argument("--image-tool-dry-run", action="store_true", help="Execute image_tool.py with --dry-run.")
    parser.add_argument("--approval-file", type=pathlib.Path, help="Approval created after the user reviews every page and explicitly starts generation.")
    args = parser.parse_args(argv)
    validate_extra(args.extra)

    if not args.image_tool.exists() and not args.dry_run:
        raise SystemExit(f"image tool not found: {args.image_tool}")

    pack = read_json(args.prompt_pack)
    raw_screens = pack.get("screens")
    if not isinstance(raw_screens, list) or not raw_screens:
        raise SystemExit("prompt_pack.json must contain a non-empty screens array.")
    screens = validate_screens(raw_screens)

    try:
        only = {
            screen_id({"screen_id": value}, index)
            for index, value in enumerate(args.only_screen or [])
        }
    except ValueError as exc:
        raise SystemExit(f"Invalid --only-screen value: {exc}") from exc
    available_screen_ids = {screen_id(screen, index) for index, screen in enumerate(screens)}
    unknown_screen_ids = sorted(only - available_screen_ids)
    if unknown_screen_ids:
        raise SystemExit("Requested screen IDs are not present in the prompt pack: " + ", ".join(unknown_screen_ids))
    approval: dict[str, Any]
    if args.dry_run or args.image_tool_dry_run:
        approval = {"approved": False, "required_for_real_generation": True, "skipped": "non-generating preview"}
    else:
        approval = validate_approval(args.prompt_pack, args.approval_file, only)

    requested_sizes: set[str] = set()
    requested_operations: set[str] = set()
    for index, screen in enumerate(screens):
        sid = screen_id(screen, index)
        if only and sid not in only:
            continue
        params = screen.get("backend_params") if isinstance(screen.get("backend_params"), dict) else {}
        requested_sizes.add(args.size or infer_size(str(params.get("aspect_ratio") or ""), args.default_size))
        refs, _ = references_for_screen(screen, args.prompt_pack, args.reference_dir)
        mode = args.mode if args.mode != "auto" else ("edit" if refs else "generate")
        requested_operations.add(mode)

    missing_reference_sets: dict[str, list[str]] = {}
    for index, screen in enumerate(screens):
        sid = screen_id(screen, index)
        if only and sid not in only:
            continue
        _, missing_refs = references_for_screen(screen, args.prompt_pack, args.reference_dir)
        if missing_refs:
            missing_reference_sets[sid] = missing_refs
    if missing_reference_sets and not (args.dry_run or args.image_tool_dry_run):
        details = "; ".join(
            f"screen_{sid}: {', '.join(names)}" for sid, names in sorted(missing_reference_sets.items())
        )
        raise SystemExit(
            "Real generation is blocked because declared reference images are missing. "
            "Restore the references or update the prompt pack and obtain fresh approval. " + details
        )

    supported_sizes = {item.strip() for item in args.supported_sizes.split(",") if item.strip()}
    unsupported_sizes = sorted(requested_sizes - supported_sizes)
    if unsupported_sizes:
        raise SystemExit(
            "Requested size(s) are not in --supported-sizes: " + ", ".join(unsupported_sizes)
            + ". Use a documented model size or explicitly update --supported-sizes."
        )

    preflight: dict[str, Any]
    if args.dry_run or args.image_tool_dry_run or args.skip_backend_check:
        preflight = {"ok": True, "skipped": True, "reason": "dry run or explicit skip"}
    else:
        check_cmd = [
            sys.executable,
            str(SCRIPT_DIR / "check_image_backend.py"),
            "--endpoint",
            args.endpoint,
            "--supported-sizes",
            args.supported_sizes,
            "--timeout",
            str(min(args.timeout, 30)),
        ]
        if args.model:
            check_cmd.extend(["--model", args.model])
        if args.base_url:
            check_cmd.extend(["--base-url", args.base_url])
        for operation in sorted(requested_operations):
            check_cmd.extend(["--operation", operation])
        for size in sorted(requested_sizes):
            check_cmd.extend(["--size", size])
        checked = subprocess.run(check_cmd, text=True, capture_output=True)
        try:
            preflight = json.loads(checked.stdout)
        except json.JSONDecodeError:
            preflight = {"ok": False, "stdout": checked.stdout, "stderr": checked.stderr}
        if checked.returncode != 0:
            raise SystemExit("Image backend preflight failed:\n" + json.dumps(preflight, ensure_ascii=False, indent=2))

    prompt_dir = args.output_dir / "prompts"
    image_dir = args.output_dir / "images"
    response_dir = args.output_dir / "responses"
    log_dir = args.output_dir / "logs"
    manifest_path = args.output_dir / "generation_manifest.json"
    if not (args.dry_run or args.image_tool_dry_run):
        existing_outputs = [
            image_dir / f"screen_{screen_id(screen, index)}.png"
            for index, screen in enumerate(screens)
            if (not only or screen_id(screen, index) in only)
            and (image_dir / f"screen_{screen_id(screen, index)}.png").exists()
        ]
        if existing_outputs:
            raise SystemExit(
                "Refusing to overwrite original screen images: "
                + ", ".join(str(path) for path in existing_outputs)
            )
    args.output_dir.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, Any] = {
        "prompt_pack": str(args.prompt_pack.resolve()),
        "image_tool": str(args.image_tool.resolve()),
        "model": args.model,
        "mode": args.mode,
        "endpoint": args.endpoint,
        "base_url": args.base_url or "AI_GATEWAY_BASE_URL",
        "backend_preflight": preflight,
        "user_approval": approval,
        "dry_run": args.dry_run,
        "image_tool_dry_run": args.image_tool_dry_run,
        "generation_policy": "one independent image-model call per screen",
        "original_screen_dir": str(image_dir.resolve()),
        "deliverables": {
            "original_screens": [],
            "note": "Each expected image is a final original screen. Preserve it for delivery and local assembly.",
        },
        "screens": [],
    }

    failures = 0
    for index, screen in enumerate(screens):
        sid = screen_id(screen, index)
        if only and sid not in only:
            continue

        params = screen.get("backend_params") if isinstance(screen.get("backend_params"), dict) else {}
        aspect_ratio = str(params.get("aspect_ratio") or "")
        render_size = args.size or infer_size(aspect_ratio, args.default_size)
        prompt_text = prompt_for_screen(pack, screen, render_size)
        prompt_path = prompt_dir / f"screen_{sid}.txt"
        write_text(prompt_path, prompt_text)

        refs, missing_refs = references_for_screen(screen, args.prompt_pack, args.reference_dir)
        mode = args.mode
        if mode == "auto":
            mode = "edit" if refs else "generate"

        output_path = image_dir / f"screen_{sid}.png"
        manifest["deliverables"]["original_screens"].append(str(output_path.resolve()))
        response_path = response_dir / f"screen_{sid}.json"
        cmd = build_command(args, mode, prompt_path, output_path, response_path, refs, aspect_ratio)
        result = run_command(cmd, args.dry_run)
        write_text(log_dir / f"screen_{sid}.command.txt", shell_join(cmd) + "\n")
        write_text(log_dir / f"screen_{sid}.stdout.txt", result["stdout"])
        write_text(log_dir / f"screen_{sid}.stderr.txt", result["stderr"])

        if args.dry_run or args.image_tool_dry_run or result["returncode"] != 0:
            artifact_validation = {
                "ok": None,
                "skipped": True,
                "reason": "non-generating preview or image tool failure",
            }
        else:
            artifact_validation = inspect_output_image(output_path)

        if result["returncode"] != 0 or artifact_validation.get("ok") is False:
            failures += 1

        manifest["screens"].append(
            {
                "screen_id": screen.get("screen_id", sid),
                "mode": mode,
                "aspect_ratio": aspect_ratio,
                "prompt_file": str(prompt_path.resolve()),
                "expected_image": str(output_path.resolve()),
                "artifact_role": "final_original_screen",
                "response_json": str(response_path.resolve()),
                "references": [str(ref) for ref in refs],
                "missing_references": missing_refs,
                "command": cmd,
                "command_text": shell_join(cmd),
                "returncode": result["returncode"],
                "executed": result["executed"],
                "duration_seconds": result["duration_seconds"],
                "artifact_validation": artifact_validation,
            }
        )

    write_json(manifest_path, manifest)
    print(json.dumps({"manifest": str(manifest_path.resolve()), "failures": failures}, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
