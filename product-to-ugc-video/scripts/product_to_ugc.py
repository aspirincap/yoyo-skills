#!/usr/bin/env python3
"""Generate character-led UGC assets from a product image plus description.

Workflow:
1. Plan a character-centric UGC sequence.
2. Generate a stable character reference image wearing or using the product.
3. Generate a sequence of continuous keyframes for the same character.
4. Generate video segments from adjacent first/last keyframes.
5. Optionally merge generated segments into one deliverable.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import textwrap
import time
from typing import Any

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from aicreative_mcp import Client, MCPError, model_default, validate, prepare_credit_commands

SKILL_DIR = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_IMAGE_MODEL = model_default("image")
DEFAULT_VIDEO_MODEL = os.getenv("AICREATIVE_VIDEO_MODEL_ID", "1108")
DEFAULT_TRIM_TAIL_SECONDS = 0.333


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Turn a product image plus description into a character-led UGC project "
            "with a character reference, continuous keyframes, video segments, and "
            "an optional merged video."
        ),
    )
    parser.add_argument("--product-image", required=True, help="Primary product image path.")
    parser.add_argument("--description", help="Product description text.")
    parser.add_argument("--description-file", help="Read product description from a UTF-8 file.")
    parser.add_argument("--product-name")
    parser.add_argument("--brand-name")
    parser.add_argument("--platform", default="TikTok")
    parser.add_argument("--language", default="zh-CN")
    parser.add_argument("--tone", default="natural, conversational, creator-style")
    parser.add_argument("--target-audience", default="general mobile-first social shoppers")
    parser.add_argument("--creator-gender", default="not specified")
    parser.add_argument("--creator-age-range", default="adult creator appropriate for the product")
    parser.add_argument("--creator-style", default="authentic everyday creator appropriate for the product")
    parser.add_argument("--scene-setting", default="a realistic everyday setting appropriate for the product use case")
    parser.add_argument("--character-reference", help="Optional existing character reference image.")
    parser.add_argument("--segment-count", type=int, default=3)
    parser.add_argument("--segment-duration", type=int, default=8)
    parser.add_argument("--aspect-ratio", default="9:16")
    parser.add_argument("--image-model", default=DEFAULT_IMAGE_MODEL)
    parser.add_argument("--video-model", default=DEFAULT_VIDEO_MODEL)
    parser.add_argument("--generate-audio", action=argparse.BooleanOptionalAction, default=True,
                        help="Native video audio; the default Wan 2.7 model requires it enabled.")
    parser.add_argument("--project-name")
    parser.add_argument("--project-dir")
    parser.add_argument("--output-root", default="outputs/product_to_ugc")
    parser.add_argument("--plan-file", help="Use an existing plan JSON file.")
    parser.add_argument("--heuristic-plan", action="store_true", help="Skip planner API and build a local plan.")
    parser.add_argument("--planner-only", action="store_true", help="Stop after writing planning outputs.")
    parser.add_argument("--skip-character-generation", action="store_true")
    parser.add_argument("--skip-frame-generation", action="store_true")
    parser.add_argument("--skip-video-generation", action="store_true")
    parser.add_argument("--skip-merge", action="store_true")
    parser.add_argument(
        "--image-endpoint",
        choices=["mcp"],
        default="mcp",
        help="Forwarded to scripts/image_tool.py.",
    )
    parser.add_argument("--image-size", help="Override generated image size.")
    parser.add_argument("--image-timeout", type=int, default=240)
    parser.add_argument("--video-timeout", type=int, default=240)
    parser.add_argument("--max-polls", type=int, default=120)
    parser.add_argument("--poll-interval", type=float, default=8.0)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def read_description(args: argparse.Namespace) -> str:
    if args.description and args.description_file:
        raise SystemExit("Use either --description or --description-file, not both.")
    if args.description_file:
        return pathlib.Path(args.description_file).read_text(encoding="utf-8").strip()
    if args.description:
        return args.description.strip()
    raise SystemExit("--description or --description-file is required.")


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value or f"ugc-{int(time.time())}"


def heuristic_plan(args: argparse.Namespace, description: str) -> dict[str, Any]:
    product_name = args.product_name or "this product"
    frame_count = args.segment_count + 1
    frames: list[dict[str, Any]] = []
    segments: list[dict[str, Any]] = []
    beat_names = ["hook", "demo", "comfort", "proof", "cta", "lifestyle"]

    for index in range(frame_count):
        frame_id = f"frame_{index + 1:02d}"
        beat = beat_names[index] if index < len(beat_names) else "demo"
        action_note = [
            "creator notices the product and begins engaging with it",
            "creator demonstrates one ordinary use of the product based on the supplied description",
            "creator shows a visible product detail without inventing a performance claim",
            "creator continues the same product interaction, showing real-life continuity",
            "creator slows slightly and lands in a confident recommendation pose",
        ]
        progression = action_note[index] if index < len(action_note) else "creator continues the action naturally"
        prompt = (
            f"Vertical UGC keyframe of the same {args.creator_style}; gender: {args.creator_gender}; "
            f"age: {args.creator_age_range}; setting: {args.scene_setting}. The creator is using or showcasing {product_name}. "
            f"Preserve the same face, hairstyle, build, outfit styling, and product details across all frames. "
            f"Action for this frame: {progression}. Product description: {description}. "
            "Keep the image photoreal, candid, mobile-shot, and believable."
        )
        voiceover = [
            "先看一下它在真实场景里的使用效果。",
            "这个细节解决了我最在意的使用问题。",
            "实际操作很直观，产品特点也看得清楚。",
            "这里用近景补充一个可验证的产品细节。",
            "如果这正是你需要的使用场景，可以进一步了解。",
        ]
        frames.append(
            {
                "id": frame_id,
                "beat": beat,
                "purpose": f"Advance the creator story beat {index + 1}.",
                "action_progression": progression,
                "prompt": prompt,
                "voiceover": voiceover[index] if index < len(voiceover) else voiceover[-1],
            }
        )

    for index in range(args.segment_count):
        segment_id = f"segment_{index + 1:02d}"
        segments.append(
            {
                "id": segment_id,
                "from_frame": f"frame_{index + 1:02d}",
                "to_frame": f"frame_{index + 2:02d}",
                "goal": "Create a realistic micro-transition between adjacent creator keyframes.",
                "video_prompt": (
                    f"Create an {args.segment_duration}-second vertical UGC clip using the first frame and last frame as exact anchors. "
                    f"Keep the same creator, same outfit, same product, same environment, and the same time progression. "
                    f"Motion should be subtle and realistic, like handheld creator footage for {product_name}. "
                    "Do not change identity, wardrobe, or product shape."
                ),
                "duration_seconds": args.segment_duration,
                "tail_trim_seconds": DEFAULT_TRIM_TAIL_SECONDS,
            }
        )

    return {
        "concept_title": f"{product_name} character-led UGC",
        "selected_angle": "A creator demonstrates an ordinary product interaction and visible details.",
        "creator_profile": {
            "identity_summary": f"{args.creator_style}, {args.creator_gender}, age {args.creator_age_range}",
            "appearance_rules": [
                "Keep the same face, hairstyle, body type, and skin tone in every frame.",
                "Keep the product color, structure, and silhouette unchanged.",
                "Keep creator styling consistent with the supplied creator and scene brief.",
            ],
            "product_wear_rule": "The same product should remain clearly visible and be handled as described across all frames.",
            "scene_rule": "Keep the setting, ambient light, and mobile-shot realism consistent while allowing slight time progression.",
        },
        "character_reference_prompt": (
            f"Create a photoreal vertical UGC creator portrait of a {args.creator_style}, {args.creator_gender}, "
            f"age {args.creator_age_range}, in {args.scene_setting}. The creator is demonstrating {product_name} as described. "
            f"Preserve product details from the reference image. Product description: {description}. "
            "The shot should feel like a premium but natural creator reference photo, clean face visibility, mobile-shot realism."
        ),
        "global_style": {
            "visual_direction": (
                "Photoreal smartphone UGC, soft cinematic natural light, subtle movement energy, premium but candid."
            ),
            "continuity_rules": [
                "Keep the same creator identity in all images.",
                "Keep the product exact and recognizable.",
                "Advance action gradually, not abruptly.",
            ],
            "motion_rules": [
                "Use subtle body movement and camera drift only.",
                "Keep transitions realistic for adjacent-frame interpolation.",
            ],
        },
        "frames": frames,
        "segments": segments,
    }


def validate_plan(plan: dict[str, Any], expected_segments: int) -> None:
    frames = plan.get("frames")
    segments = plan.get("segments")
    if not isinstance(frames, list) or not isinstance(segments, list):
        raise RuntimeError("Plan must contain list fields: frames and segments.")
    if len(frames) != expected_segments + 1:
        raise RuntimeError(f"Expected {expected_segments + 1} frames, got {len(frames)}.")
    if len(segments) != expected_segments:
        raise RuntimeError(f"Expected {expected_segments} segments, got {len(segments)}.")
    frame_ids = {frame.get("id") for frame in frames if isinstance(frame, dict)}
    for segment in segments:
        if not isinstance(segment, dict):
            raise RuntimeError("Segment entries must be objects.")
        if segment.get("from_frame") not in frame_ids or segment.get("to_frame") not in frame_ids:
            raise RuntimeError(f"Segment references unknown frames: {segment}")


def write_text(path: pathlib.Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_json(path: pathlib.Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def ensure_file(path: pathlib.Path) -> pathlib.Path:
    if not path.exists():
        raise SystemExit(f"File not found: {path}")
    if not path.is_file():
        raise SystemExit(f"Path is not a file: {path}")
    return path.resolve()


def copy_input_file(source: pathlib.Path, target: pathlib.Path) -> pathlib.Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() != target.resolve():
        shutil.copy2(source, target)
    return target.resolve()


def parse_saved_paths(stdout: str) -> list[pathlib.Path]:
    paths: list[pathlib.Path] = []
    for line in stdout.splitlines():
        if line.startswith("saved="):
            paths.append(pathlib.Path(line.split("=", 1)[1].strip()))
    return paths


def run_cli(cmd: list[str], dry_run: bool) -> dict[str, Any]:
    if dry_run:
        return {"returncode": 0, "stdout": "", "stderr": "", "executed": False, "command": cmd}
    completed = subprocess.run(
        cmd,
        check=False,
        text=True,
        capture_output=True,
    )
    return {
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "executed": True,
        "command": cmd,
    }


def try_cli_candidates(
    commands: list[tuple[str, list[str]]],
    dry_run: bool,
) -> tuple[str, dict[str, Any]]:
    if len(commands) != 1:
        raise RuntimeError("Select one MCP modelConfigId; automatic model fallback is disabled.")
    model_name, command = commands[0]
    return model_name, run_cli(command, dry_run)


def build_project_paths(project_dir: pathlib.Path) -> dict[str, pathlib.Path]:
    return {
        "root": project_dir,
        "inputs": project_dir / "inputs",
        "planning": project_dir / "planning",
        "prompts": project_dir / "prompts",
        "character_reference": project_dir / "character_reference",
        "character_reference_json": project_dir / "character_reference" / "responses",
        "continuous_frames": project_dir / "continuous_frames",
        "continuous_frames_json": project_dir / "continuous_frames" / "responses",
        "video_segments": project_dir / "video_segments",
        "video_json": project_dir / "video_segments" / "responses",
        "manifests": project_dir / "manifests",
        "logs": project_dir / "logs",
        "merged": project_dir / "merged",
    }


def planner_metadata(plan: dict[str, Any]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    for key in ("concept_title", "selected_angle", "creator_profile", "global_style"):
        if key in plan:
            metadata[key] = plan[key]
    return metadata


def image_size_for_ratio(ratio: str) -> str:
    if ratio == "9:16":
        return "1152x2048"
    if ratio == "16:9":
        return "2048x1152"
    return "1024x1024"


def character_reference_output_path(paths: dict[str, pathlib.Path]) -> pathlib.Path:
    return paths["character_reference"] / "character_reference.png"


def frame_output_path(paths: dict[str, pathlib.Path], frame_id: str) -> pathlib.Path:
    return paths["continuous_frames"] / f"{frame_id}.png"


def segment_output_path(paths: dict[str, pathlib.Path], segment_id: str) -> pathlib.Path:
    return paths["video_segments"] / f"{segment_id}.mp4"


def plan_summary_markdown(plan: dict[str, Any], planner_used: str) -> str:
    lines = [
        f"# {plan.get('concept_title', 'Character UGC Plan')}",
        "",
        f"- planner: `{planner_used}`",
        f"- angle: {plan.get('selected_angle', '')}",
        f"- identity: {plan.get('creator_profile', {}).get('identity_summary', '')}",
        "",
        "## Frames",
        "",
    ]
    for frame in plan.get("frames", []):
        if not isinstance(frame, dict):
            continue
        lines.append(
            f"- `{frame.get('id')}`: {frame.get('action_progression', '')}"
        )
    lines.extend(["", "## Segments", ""])
    for segment in plan.get("segments", []):
        if not isinstance(segment, dict):
            continue
        lines.append(
            f"- `{segment.get('id')}`: {segment.get('from_frame')} -> {segment.get('to_frame')} "
            f"({segment.get('duration_seconds', '')}s)"
        )
    return "\n".join(lines).strip() + "\n"


def save_plan_artifacts(plan: dict[str, Any], paths: dict[str, pathlib.Path], planner_used: str) -> None:
    clean_plan = {key: value for key, value in plan.items() if not key.startswith("_planner_")}
    write_json(paths["planning"] / "plan.json", clean_plan)
    write_text(paths["planning"] / "plan_summary.md", plan_summary_markdown(clean_plan, planner_used))
    if "_planner_request" in plan:
        write_json(paths["planning"] / "planner_request.json", plan["_planner_request"])
    if "_planner_response" in plan:
        write_json(paths["planning"] / "planner_response.json", plan["_planner_response"])


def manifest_entry(command: list[str], result: dict[str, Any], expected_output: str) -> dict[str, Any]:
    return {
        "command": command,
        "executed": result["executed"],
        "returncode": result["returncode"],
        "expected_output": expected_output,
        "stdout": result["stdout"],
        "stderr": result["stderr"],
    }


def build_image_edit_command(
    args: argparse.Namespace,
    model_name: str,
    prompt_path: pathlib.Path,
    output_path: pathlib.Path,
    json_path: pathlib.Path,
    reference_images: list[pathlib.Path],
) -> list[str]:
    cmd = [
        sys.executable,
        str((pathlib.Path(__file__).parent / "image_tool.py").resolve()),
        "edit",
        "--model",
        model_name,
        "--prompt-file",
        str(prompt_path),
        "--endpoint",
        args.image_endpoint,
        "--size",
        args.image_size or image_size_for_ratio(args.aspect_ratio),
        "--output",
        str(output_path),
        "--save-json",
        str(json_path),
        "--timeout",
        str(args.image_timeout),
    ]
    if not args.image_size:
        cmd.extend(["--ratio", args.aspect_ratio])
    for image_path in reference_images:
        cmd.extend(["--image", str(image_path)])
    if getattr(args, "credit_review", None):
        cmd.extend(["--credit-review", str(args.credit_review)])
    return cmd


def build_video_command(
    args: argparse.Namespace,
    model_name: str,
    segment: dict[str, Any],
    from_frame: pathlib.Path,
    to_frame: pathlib.Path,
    output_path: pathlib.Path,
    json_path: pathlib.Path,
    prompt_path: pathlib.Path,
) -> list[str]:
    cmd = [
        sys.executable, str(pathlib.Path(__file__).parent / "generate_video.py"),
        "--model", model_name, "--prompt-file", str(prompt_path),
        "--duration", str(segment.get("duration_seconds", args.segment_duration)),
        "--ratio", args.aspect_ratio, "--generate-audio" if args.generate_audio else "--no-generate-audio",
        "--first-frame", str(from_frame), "--last-frame", str(to_frame),
        "--output", str(output_path), "--save-json", str(json_path),
        "--poll-interval", str(args.poll_interval), "--max-polls", str(args.max_polls),
        "--download-timeout", str(args.video_timeout),
    ]
    if getattr(args, "credit_review", None):
        cmd.extend(["--credit-review", str(args.credit_review)])
    return cmd


def prepare_project_credits(args, plan, paths, product, character):
    """Quote the entire dependency chain before creating its first paid asset."""
    jobs = []
    char_path = character or character_reference_output_path(paths)
    prompt = paths["prompts"] / "character_reference.prompt.txt"
    write_text(prompt, plan["character_reference_prompt"].strip()+"\n")
    if not character and not args.skip_character_generation:
        jobs.append(build_image_edit_command(args, args.image_model, prompt, char_path,
                    paths["character_reference_json"] / "character_reference.json", [product]))
    previous = None
    frames = {}
    for frame in plan["frames"]:
        fid = frame["id"]
        prompt = paths["prompts"] / "frames" / f"{fid}.prompt.txt"
        write_text(prompt, frame["prompt"].strip()+"\n")
        output = frame_output_path(paths, fid)
        frames[fid] = output
        if not args.skip_frame_generation:
            refs = [product, char_path] + ([previous] if previous else [])
            jobs.append(build_image_edit_command(args, args.image_model, prompt, output,
                        paths["continuous_frames_json"] / f"{fid}.json", refs))
        previous = output
    if not args.skip_video_generation:
        for segment in plan["segments"]:
            sid = segment["id"]
            prompt = paths["prompts"] / "segments" / f"{sid}.prompt.txt"
            write_text(prompt, segment["video_prompt"].strip()+"\n")
            jobs.append(build_video_command(args, args.video_model, segment,
                        frames[segment["from_frame"]], frames[segment["to_frame"]],
                        segment_output_path(paths, sid), paths["video_json"] / f"{sid}.json", prompt))
    review = paths["root"] / "generation.credits.json"
    prepare_credit_commands(jobs, review)
    args.credit_review = review


def ffmpeg_available() -> bool:
    try:
        completed = subprocess.run(
            ["ffmpeg", "-version"],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return False
    return completed.returncode == 0


def build_merge_command(segment_paths: list[pathlib.Path], concat_file: pathlib.Path, output_path: pathlib.Path) -> list[str]:
    concat_lines = [f"file '{path.as_posix()}'" for path in segment_paths]
    write_text(concat_file, "\n".join(concat_lines) + "\n")
    return [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_file),
        "-c",
        "copy",
        str(output_path),
    ]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    description = read_description(args)
    if not (args.heuristic_plan or args.plan_file):
        raise SystemExit("This MCP branch has no text gateway. Supply --plan-file from your agent, or --heuristic-plan for local planning.")
    if args.heuristic_plan and args.plan_file:
        raise SystemExit("Choose --plan-file or --heuristic-plan, not both.")
    available_models = []
    planner_model = "plan_file" if args.plan_file else "heuristic"
    image_candidates = [args.image_model]
    video_candidates = [args.video_model]

    product_image = ensure_file(pathlib.Path(args.product_image))
    character_reference_input = ensure_file(pathlib.Path(args.character_reference)) if args.character_reference else None

    project_slug = args.project_name or slugify(args.product_name or pathlib.Path(args.product_image).stem)
    project_dir = (
        pathlib.Path(args.project_dir)
        if args.project_dir
        else pathlib.Path(args.output_root) / project_slug
    ).resolve()
    paths = build_project_paths(project_dir)
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)

    copied_product = copy_input_file(product_image, paths["inputs"] / product_image.name)
    copied_character_input = None
    if character_reference_input:
        copied_character_input = copy_input_file(
            character_reference_input,
            paths["inputs"] / "character_reference" / character_reference_input.name,
        )
    write_text(paths["inputs"] / "description.txt", description + "\n")

    planner_used = "plan_file"
    if args.plan_file:
        plan = json.loads(pathlib.Path(args.plan_file).read_text(encoding="utf-8"))
    elif args.heuristic_plan:
        planner_used = "heuristic"
        plan = heuristic_plan(args, description)
    validate_plan(plan, args.segment_count)
    if not (args.dry_run or args.planner_only or args.skip_video_generation):
        try:
            model = Client().call("get_model_parameters", {"modelConfigId": int(args.video_model)})["model"]
            if model.get("inputSettings", {}).get("supportRealPerson") is not True:
                raise MCPError("Character-led UGC requires a video model that supports person references; select a compatible --video-model (tested Beta: 1108).")
            for segment in plan["segments"]:
                validate({"generationType": "VIDEO", "prompt": segment["video_prompt"],
                          "frame": {"firstFrame": {"assetId": 1}, "lastFrame": {"assetId": 2}},
                          "parameters": {"count": 1, "duration": segment.get("duration_seconds", args.segment_duration),
                                         "aspectRatioKey": args.aspect_ratio, "resolutionKey": "720P",
                                         "generateAudioKey": "ON" if args.generate_audio else "OFF", "publicVisibilityKey": "OFF"}}, model, [])
        except (MCPError, ValueError) as exc:
            raise SystemExit(str(exc)) from None
    save_plan_artifacts(plan, paths, planner_used)

    project_metadata = {
        "project_name": project_slug,
        "planner": planner_used,
        "available_models": available_models,
        "resolved_models": {
            "planner": planner_model,
            "image_candidates": image_candidates,
            "video_candidates": video_candidates,
        },
        "product_name": args.product_name,
        "brand_name": args.brand_name,
        "platform": args.platform,
        "language": args.language,
        "aspect_ratio": args.aspect_ratio,
        "segment_count": args.segment_count,
        "segment_duration": args.segment_duration,
        "generate_audio": args.generate_audio,
        "dry_run": args.dry_run,
        "product_image": str(copied_product),
        "character_reference_input": str(copied_character_input) if copied_character_input else None,
        "planner_metadata": planner_metadata(plan),
    }
    write_json(paths["root"] / "project.json", project_metadata)

    if args.planner_only:
        return 0

    if not args.dry_run:
        prepare_project_credits(args, plan, paths, copied_product, copied_character_input)

    command_log: list[dict[str, Any]] = []

    character_reference_prompt_path = paths["prompts"] / "character_reference.prompt.txt"
    write_text(character_reference_prompt_path, plan["character_reference_prompt"].strip() + "\n")
    character_reference_path = copied_character_input or character_reference_output_path(paths)

    if not copied_character_input and not args.skip_character_generation:
        candidate_commands = [
            (
                model_name,
                build_image_edit_command(
                    args=args,
                    model_name=model_name,
                    prompt_path=character_reference_prompt_path,
                    output_path=character_reference_output_path(paths),
                    json_path=paths["character_reference_json"] / "character_reference.json",
                    reference_images=[copied_product],
                ),
            )
            for model_name in image_candidates
        ]
        resolved_model, result = try_cli_candidates(candidate_commands, args.dry_run)
        command_log.append(
            manifest_entry(candidate_commands[0][1], result, str(character_reference_output_path(paths)))
            | {"resolved_model": resolved_model, "stage": "character_reference"}
        )
        if result["returncode"] != 0:
            write_json(paths["logs"] / "command_log.json", command_log)
            raise SystemExit(result["stderr"] or "Character reference generation failed.")
        saved_paths = parse_saved_paths(result["stdout"])
        if saved_paths:
            character_reference_path = saved_paths[0]
        elif args.dry_run:
            character_reference_path = character_reference_output_path(paths)
        else:
            raise SystemExit("Character reference generation did not report a saved path.")

    frame_paths: dict[str, pathlib.Path] = {}
    previous_frame_path: pathlib.Path | None = None
    for frame in plan["frames"]:
        frame_id = frame["id"]
        prompt_path = paths["prompts"] / "frames" / f"{frame_id}.prompt.txt"
        write_text(prompt_path, frame["prompt"].strip() + "\n")
        output_path = frame_output_path(paths, frame_id)
        json_path = paths["continuous_frames_json"] / f"{frame_id}.json"
        frame_paths[frame_id] = output_path

        if args.skip_frame_generation:
            previous_frame_path = output_path
            continue

        reference_images = [copied_product, character_reference_path]
        if previous_frame_path is not None:
            reference_images.append(previous_frame_path)

        candidate_commands = [
            (
                model_name,
                build_image_edit_command(
                    args=args,
                    model_name=model_name,
                    prompt_path=prompt_path,
                    output_path=output_path,
                    json_path=json_path,
                    reference_images=reference_images,
                ),
            )
            for model_name in image_candidates
        ]
        resolved_model, result = try_cli_candidates(candidate_commands, args.dry_run)
        command_log.append(
            manifest_entry(candidate_commands[0][1], result, str(output_path))
            | {"resolved_model": resolved_model, "stage": "continuous_frame", "frame_id": frame_id}
        )
        if result["returncode"] != 0:
            write_json(paths["logs"] / "command_log.json", command_log)
            raise SystemExit(result["stderr"] or f"Frame generation failed for {frame_id}.")
        saved_paths = parse_saved_paths(result["stdout"])
        if saved_paths:
            previous_frame_path = saved_paths[0]
            frame_paths[frame_id] = saved_paths[0]
        elif args.dry_run:
            previous_frame_path = output_path
        else:
            raise SystemExit(f"Frame generation did not report a saved path for {frame_id}.")

    assembly_manifest: dict[str, Any] = {
        "trim_tail_seconds": DEFAULT_TRIM_TAIL_SECONDS,
        "aspect_ratio": args.aspect_ratio,
        "character_reference": str(character_reference_path),
        "segments": [],
    }

    segment_paths: list[pathlib.Path] = []
    for index, segment in enumerate(plan["segments"], start=1):
        segment_id = segment["id"]
        prompt_path = paths["prompts"] / "segments" / f"{segment_id}.prompt.txt"
        voiceover_path = paths["prompts"] / "segments" / f"{segment_id}.voiceover.txt"
        from_frame = frame_paths[segment["from_frame"]]
        to_frame = frame_paths[segment["to_frame"]]
        from_voiceover = ""
        frame_index = index - 1
        if frame_index < len(plan["frames"]):
            from_voiceover = str(plan["frames"][frame_index].get("voiceover", "")).strip()
        write_text(prompt_path, segment["video_prompt"].strip() + "\n")
        write_text(voiceover_path, from_voiceover + "\n")

        output_path = segment_output_path(paths, segment_id)
        json_path = paths["video_json"] / f"{segment_id}.json"
        segment_paths.append(output_path)
        assembly_manifest["segments"].append(
            {
                "id": segment_id,
                "file": str(output_path),
                "from_frame": str(from_frame),
                "to_frame": str(to_frame),
                "duration_seconds": segment.get("duration_seconds", args.segment_duration),
                "tail_trim_seconds": segment.get("tail_trim_seconds", DEFAULT_TRIM_TAIL_SECONDS),
                "voiceover": from_voiceover,
            }
        )

        if args.skip_video_generation:
            continue

        candidate_commands = [
            (
                model_name,
                build_video_command(
                    args=args,
                    model_name=model_name,
                    segment=segment,
                    from_frame=from_frame,
                    to_frame=to_frame,
                    output_path=output_path,
                    json_path=json_path,
                    prompt_path=prompt_path,
                ),
            )
            for model_name in video_candidates
        ]
        resolved_model, result = try_cli_candidates(candidate_commands, args.dry_run)
        command_log.append(
            manifest_entry(candidate_commands[0][1], result, str(output_path))
            | {"resolved_model": resolved_model, "stage": "video_segment", "segment_id": segment_id}
        )
        if result["returncode"] != 0:
            write_json(paths["logs"] / "command_log.json", command_log)
            raise SystemExit(result["stderr"] or f"Video generation failed for {segment_id}.")

    write_json(paths["manifests"] / "assembly_manifest.json", assembly_manifest)

    merged_output = paths["merged"] / "final_ugc.mp4"
    merge_manifest = {
        "output": str(merged_output),
        "segment_files": [str(path) for path in segment_paths],
        "ffmpeg_available": ffmpeg_available(),
    }

    if not args.skip_merge and not args.skip_video_generation:
        if args.dry_run:
            concat_file = paths["manifests"] / "ffmpeg_concat.txt"
            merge_command = build_merge_command(segment_paths, concat_file, merged_output)
            command_log.append(
                {
                    "stage": "merge",
                    "command": merge_command,
                    "executed": False,
                    "returncode": 0,
                    "expected_output": str(merged_output),
                    "stdout": "",
                    "stderr": "",
                }
            )
        elif ffmpeg_available():
            concat_file = paths["manifests"] / "ffmpeg_concat.txt"
            merge_command = build_merge_command(segment_paths, concat_file, merged_output)
            result = run_cli(merge_command, dry_run=False)
            command_log.append(
                manifest_entry(merge_command, result, str(merged_output))
                | {"stage": "merge"}
            )
            if result["returncode"] == 0:
                merge_manifest["merged_file"] = str(merged_output)
            else:
                merge_manifest["merge_error"] = result["stderr"]
        else:
            merge_manifest["merge_error"] = "ffmpeg not found on PATH"

    write_json(paths["manifests"] / "merge_manifest.json", merge_manifest)
    write_json(paths["logs"] / "command_log.json", command_log)
    if merge_manifest.get("merge_error"):
        print(merge_manifest["merge_error"], file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except MCPError as exc:
        raise SystemExit(str(exc)) from None
