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
import urllib.error
import urllib.request
from typing import Any


DEFAULT_BASE_URL = None
DEFAULT_PLANNER_MODEL = "auto"
DEFAULT_IMAGE_MODEL = "auto"
DEFAULT_VIDEO_MODEL = "auto"
DEFAULT_TRIM_TAIL_SECONDS = 0.333
PLANNER_MODEL_CANDIDATES = [
    "gpt-5.4-mini",
    "gpt-5.4",
    "gpt-5.5",
    "gpt-5.3-codex",
    "gpt-5.2-codex",
    "gpt-5.1-codex",
]
IMAGE_MODEL_CANDIDATES = [
    "gpt-image-2",
    "gemini-3.1-flash-image-preview",
    "gemini-3-pro-image-preview",
    "wan2.7-image",
    "wan2.7-image-pro",
    "wan2.6-t2i",
]
VIDEO_MODEL_CANDIDATES = [
    "veo-3.1-fast-generate-001",
    "doubao-seedance-2-0-fast-260128",
    "doubao-seedance-2-0-260128",
    "wan2.7-i2v",
    "wan2.6-i2v-flash",
    "kling-v3",
]
SYSTEM_PROMPT = """You are a short-form UGC creative director.
Return strict JSON only.

Design a character-first UGC workflow where:
- a single stable creator persona is established first
- each following keyframe shows the same person in the same outfit/product
- each frame advances the action slightly
- adjacent frames will be used as first/last frame anchors for video generation

Keep the product faithful to the supplied reference image.
Keep actions realistic and feasible for AI image/video generation.
Avoid unsupported claims.
"""


class ApiError(RuntimeError):
    def __init__(self, status: int | str, body: Any) -> None:
        super().__init__(f"HTTP {status}: {body}")
        self.status = status
        self.body = body


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
    parser.add_argument("--planner-model", default=DEFAULT_PLANNER_MODEL)
    parser.add_argument("--image-model", default=DEFAULT_IMAGE_MODEL)
    parser.add_argument("--video-model", default=DEFAULT_VIDEO_MODEL)
    parser.add_argument(
        "--probe-models",
        action="store_true",
        help="Inspect /v1/models and auto-select planner/image/video fallbacks.",
    )
    parser.add_argument("--project-name")
    parser.add_argument("--project-dir")
    parser.add_argument("--output-root", default="outputs/product_to_ugc")
    parser.add_argument(
        "--api-key-env",
        action="append",
        default=["UGC_API_KEY", "LLM_API_KEY", "NEWAPI_API_KEY", "PRODUCT_UGC_API_KEY"],
        help="Environment variable to read the API key from. Can be repeated.",
    )
    parser.add_argument("--api-key", help="API key. Prefer env vars for shell history safety.")
    parser.add_argument("--base-url", default=os.getenv("UGC_API_BASE_URL") or os.getenv("LLM_API_BASE_URL") or DEFAULT_BASE_URL)
    parser.add_argument("--plan-file", help="Use an existing plan JSON file.")
    parser.add_argument("--heuristic-plan", action="store_true", help="Skip planner API and build a local plan.")
    parser.add_argument("--planner-only", action="store_true", help="Stop after writing planning outputs.")
    parser.add_argument("--skip-character-generation", action="store_true")
    parser.add_argument("--skip-frame-generation", action="store_true")
    parser.add_argument("--skip-video-generation", action="store_true")
    parser.add_argument("--skip-merge", action="store_true")
    parser.add_argument(
        "--image-endpoint",
        choices=["auto", "images", "chat"],
        default="auto",
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


def get_api_key(args: argparse.Namespace) -> str:
    if args.api_key:
        return args.api_key
    for env_name in args.api_key_env:
        value = os.getenv(env_name)
        if value:
            return value
    raise SystemExit(
        "API key not found. Set UGC_API_KEY/LLM_API_KEY or pass --api-key. "
        "You can also add env names with --api-key-env."
    )


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value or f"ugc-{int(time.time())}"


def parse_response(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def request_json(
    base_url: str,
    path: str,
    api_key: str,
    payload: dict[str, Any],
    timeout: int = 180,
) -> dict[str, Any]:
    req = urllib.request.Request(
        base_url.rstrip("/") + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = parse_response(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        body = parse_response(exc.read().decode("utf-8", errors="replace"))
        raise ApiError(exc.code, body) from exc
    except urllib.error.URLError as exc:
        raise ApiError("network_error", str(exc)) from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"Expected JSON object response, got: {data!r}")
    return data


def fetch_available_models(args: argparse.Namespace) -> list[str]:
    req = urllib.request.Request(
        args.base_url.rstrip("/") + "/v1/models",
        headers={"Authorization": f"Bearer {get_api_key(args)}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = parse_response(resp.read().decode("utf-8", errors="replace"))
    except Exception:
        return []
    if not isinstance(payload, dict):
        return []
    items = payload.get("data")
    if not isinstance(items, list):
        return []
    models = [
        item["id"]
        for item in items
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    ]
    models.sort()
    return models


def resolve_model(preferred: str, candidates: list[str], available_models: list[str]) -> str:
    if preferred != "auto":
        return preferred
    if available_models:
        for candidate in candidates:
            if candidate in available_models:
                return candidate
    return candidates[0]


def extract_message_text(data: dict[str, Any]) -> str:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError(f"Planner response missing choices: {data}")
    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise RuntimeError(f"Planner response missing message: {data}")
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts: list[str] = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                texts.append(item["text"])
        if texts:
            return "\n".join(texts)
    raise RuntimeError(f"Planner response missing textual content: {data}")


def parse_json_blob(text: str) -> dict[str, Any]:
    stripped = text.strip()
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", stripped, flags=re.DOTALL)
        if not match:
            raise
        parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise RuntimeError(f"Expected planner JSON object, got: {parsed!r}")
    return parsed


def planner_prompt(args: argparse.Namespace, description: str) -> str:
    product_name = args.product_name or "Unnamed Product"
    brand_name = args.brand_name or "Unknown Brand"
    frame_count = args.segment_count + 1
    total_duration = args.segment_count * args.segment_duration
    reference_state = "provided" if args.character_reference else "not provided"
    return textwrap.dedent(
        f"""
        Build a character-first product UGC plan.

        Context:
        - brand_name: {brand_name}
        - product_name: {product_name}
        - platform: {args.platform}
        - language: {args.language}
        - tone: {args.tone}
        - target_audience: {args.target_audience}
        - creator_gender: {args.creator_gender}
        - creator_age_range: {args.creator_age_range}
        - creator_style: {args.creator_style}
        - scene_setting: {args.scene_setting}
        - aspect_ratio: {args.aspect_ratio}
        - character_reference: {reference_state}
        - keyframe_count: {frame_count}
        - segment_count: {args.segment_count}
        - segment_duration_seconds: {args.segment_duration}
        - total_duration_seconds: {total_duration}

        Product description:
        {description}

        Return JSON with this schema:
        {{
          "concept_title": "short title",
          "selected_angle": "one sentence",
          "creator_profile": {{
            "identity_summary": "one sentence",
            "appearance_rules": ["array of stable face/body/wardrobe rules"],
            "product_wear_rule": "how the product appears on the creator",
            "scene_rule": "what stays consistent in the environment"
          }},
          "character_reference_prompt": "prompt for generating the stable hero character reference image",
          "global_style": {{
            "visual_direction": "single paragraph",
            "continuity_rules": ["array"],
            "motion_rules": ["array"]
          }},
          "frames": [
            {{
              "id": "frame_01",
              "beat": "hook/demo/proof/cta",
              "purpose": "one sentence",
              "action_progression": "small action advance from prior moment",
              "prompt": "prompt for generating this keyframe while preserving the same creator",
              "voiceover": "short spoken line in {args.language}"
            }}
          ],
          "segments": [
            {{
              "id": "segment_01",
              "from_frame": "frame_01",
              "to_frame": "frame_02",
              "goal": "one sentence",
              "video_prompt": "prompt describing motion between adjacent frames",
              "duration_seconds": {args.segment_duration},
              "tail_trim_seconds": {DEFAULT_TRIM_TAIL_SECONDS}
            }}
          ]
        }}

        Requirements:
        - Produce exactly {frame_count} frames and exactly {args.segment_count} segments.
        - Each frame must depict the same creator and the same product.
        - The action should progress slightly across each frame.
        - Voiceover lines must be concise enough for {args.segment_duration} seconds each.
        - The time shown in props like phones can change naturally across frames when helpful.
        - Return JSON only.
        """
    ).strip()


def call_planner(args: argparse.Namespace, description: str, planner_model: str) -> dict[str, Any]:
    prompt = planner_prompt(args, description)
    payload = {
        "model": planner_model,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    }
    response = request_json(
        args.base_url,
        "/v1/chat/completions",
        get_api_key(args),
        payload,
        timeout=180,
    )
    plan = parse_json_blob(extract_message_text(response))
    plan["_planner_request"] = payload
    plan["_planner_response"] = response
    return plan


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
            "creator starts moving naturally and shows how it wears",
            "creator shifts into a more active moment, emphasizing comfort and breathability",
            "creator glances at a phone and keeps moving, showing real-life continuity",
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
        "selected_angle": "A sporty creator naturally demonstrates comfort, breathability, and real-use credibility.",
        "creator_profile": {
            "identity_summary": f"{args.creator_style}, {args.creator_gender}, age {args.creator_age_range}",
            "appearance_rules": [
                "Keep the same face, hairstyle, body type, and skin tone in every frame.",
                "Keep the product color, fit, and silhouette unchanged.",
                "Keep the creator styling consistent with a modern running lifestyle.",
            ],
            "product_wear_rule": "The product should remain clearly visible as the same garment across all frames.",
            "scene_rule": "Keep the route, ambient light, and mobile-shot realism consistent while allowing slight time progression.",
        },
        "character_reference_prompt": (
            f"Create a photoreal vertical UGC creator portrait of a {args.creator_style}, {args.creator_gender}, "
            f"age {args.creator_age_range}, in {args.scene_setting}. She is wearing or holding {product_name}. "
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


def classify_model_error(stderr: str) -> bool:
    lowered = stderr.lower()
    return "model_not_found" in lowered or "no available channel for model" in lowered


def classify_retryable_error(stderr: str) -> bool:
    lowered = stderr.lower()
    retryable_markers = [
        "504 gateway time-out",
        "502 bad gateway",
        "503 service unavailable",
        "network_error",
        "timed out",
        "timeout",
    ]
    return any(marker in lowered for marker in retryable_markers)


def try_cli_candidates(
    commands: list[tuple[str, list[str]]],
    dry_run: bool,
) -> tuple[str, dict[str, Any]]:
    last_result: dict[str, Any] | None = None
    last_model = ""
    for model_name, cmd in commands:
        result = run_cli(cmd, dry_run)
        if (
            not dry_run
            and result["returncode"] != 0
            and classify_retryable_error(result["stderr"])
        ):
            time.sleep(3)
            result = run_cli(cmd, dry_run)
        if result["returncode"] == 0 or dry_run:
            return model_name, result
        last_model = model_name
        last_result = result
        if not classify_model_error(result["stderr"]):
            return model_name, result
    if last_result is None:
        raise RuntimeError("No commands were provided for candidate execution.")
    return last_model, last_result


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
        return "1024x1536"
    if ratio == "16:9":
        return "1536x1024"
    return "1024x1024"


def dimensions_for_ratio(ratio: str) -> tuple[int, int]:
    if ratio == "9:16":
        return (720, 1280)
    if ratio == "16:9":
        return (1280, 720)
    return (1024, 1024)


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


def build_image_generate_command(
    args: argparse.Namespace,
    model_name: str,
    prompt_path: pathlib.Path,
    output_path: pathlib.Path,
    json_path: pathlib.Path,
) -> list[str]:
    return [
        sys.executable,
        str((pathlib.Path(__file__).parent / "image_tool.py").resolve()),
        "generate",
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
    for image_path in reference_images:
        cmd.extend(["--image", str(image_path)])
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
    width, height = dimensions_for_ratio(args.aspect_ratio)
    cmd = [
        sys.executable,
        str((pathlib.Path(__file__).parent / "generate_video.py").resolve()),
        "--model",
        model_name,
        "--prompt-file",
        str(prompt_path),
        "--duration",
        str(segment.get("duration_seconds", args.segment_duration)),
        "--width",
        str(width),
        "--height",
        str(height),
        "--no-generate-audio",
        "--output",
        str(output_path),
        "--save-json",
        str(json_path),
        "--poll-interval",
        str(args.poll_interval),
        "--max-polls",
        str(args.max_polls),
        "--download-timeout",
        str(args.video_timeout),
    ]
    model_lower = model_name.lower()
    if "veo" in model_lower:
        cmd.extend([
            "--image",
            str(from_frame),
            "--image-field",
            "image",
            "--last-frame",
            str(to_frame),
            "--last-frame-field",
            "lastFrame",
            "--last-frame-encoding",
            "image-object",
        ])
    else:
        cmd.extend([
            "--image",
            str(from_frame),
            "--image",
            str(to_frame),
            "--image-field",
            "content",
        ])
    return cmd


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
    if not args.base_url and not (args.heuristic_plan or args.plan_file):
        raise SystemExit("Planner base URL is required. Set UGC_API_BASE_URL/LLM_API_BASE_URL or pass --base-url. Use --heuristic-plan for an offline plan.")
    available_models = fetch_available_models(args) if args.probe_models else []
    planner_model = resolve_model(args.planner_model, PLANNER_MODEL_CANDIDATES, available_models)
    image_candidates = (
        [args.image_model]
        if args.image_model != "auto"
        else [model for model in IMAGE_MODEL_CANDIDATES if not available_models or model in available_models] or IMAGE_MODEL_CANDIDATES
    )
    video_candidates = (
        [args.video_model]
        if args.video_model != "auto"
        else [model for model in VIDEO_MODEL_CANDIDATES if not available_models or model in available_models] or VIDEO_MODEL_CANDIDATES
    )

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
            paths["inputs"] / character_reference_input.name,
        )
    write_text(paths["inputs"] / "description.txt", description + "\n")

    planner_used = "plan_file"
    if args.plan_file:
        plan = json.loads(pathlib.Path(args.plan_file).read_text(encoding="utf-8"))
    elif args.heuristic_plan:
        planner_used = "heuristic"
        plan = heuristic_plan(args, description)
    else:
        planner_used = planner_model
        plan = call_planner(args, description, planner_model)
    validate_plan(plan, args.segment_count)
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
        "dry_run": args.dry_run,
        "product_image": str(copied_product),
        "character_reference_input": str(copied_character_input) if copied_character_input else None,
        "planner_metadata": planner_metadata(plan),
    }
    write_json(paths["root"] / "project.json", project_metadata)

    if args.planner_only:
        return 0

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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
