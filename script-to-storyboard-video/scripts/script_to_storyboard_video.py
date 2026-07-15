#!/usr/bin/env python3
"""Two-stage script -> approved storyboard -> video pipeline.

Stage 1:
  Generate one or more storyboard sheets from an ad script and product images.

Stage 2:
  After human approval, turn approved storyboard sheets into Seedance clips.

This wrapper uses the vendored shared media runtime:
  - image_tool.py
  - generate_video.py
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import math
import pathlib
import re
import subprocess
import sys
import time
from typing import Any

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from ai_gateway import gateway_base_url, gateway_model


IMAGE_TOOL = SCRIPT_DIR / "image_tool.py"
VIDEO_TOOL = SCRIPT_DIR / "generate_video.py"

SKILL_DIR = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = pathlib.Path("outputs/script-to-storyboard-video")
DEFAULT_BASE_URL = gateway_base_url(
    "AD_STORYBOARD_BASE_URL", "IMAGE_API_BASE_URL", "VIDEO_API_BASE_URL", skill_dir=SKILL_DIR
)
DEFAULT_API_KEY_ENVS = (
    "AI_GATEWAY_API_KEY,NEWAPI_API_KEY,OPENAI_API_KEY,"
    "PRODUCT_UGC_IMAGE_API_KEY,PRODUCT_UGC_VIDEO_API_KEY,"
    "IMAGE_API_KEY,VIDEO_API_KEY"
)
DEFAULT_IMAGE_MODEL = gateway_model(
    "image", "AD_STORYBOARD_IMAGE_MODEL", default="gpt-image-1", skill_dir=SKILL_DIR
)
DEFAULT_VIDEO_MODEL = gateway_model(
    "video", "AD_STORYBOARD_VIDEO_MODEL", default="seedance-model-id", skill_dir=SKILL_DIR
)


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-").lower()
    return cleaned or "script-to-storyboard-video"


def read_script(args: argparse.Namespace) -> str:
    if getattr(args, "script", None) and getattr(args, "script_file", None):
        raise SystemExit("Use either --script or --script-file, not both.")
    if getattr(args, "script_file", None):
        return pathlib.Path(args.script_file).expanduser().read_text(encoding="utf-8").strip()
    if getattr(args, "script", None):
        return args.script.strip()
    raise SystemExit("--script or --script-file is required.")


def split_segments(duration: int, segment_duration: int, count: int | None = None) -> list[tuple[int, int]]:
    if duration <= 0:
        raise SystemExit("--duration must be positive.")
    if segment_duration <= 0 or segment_duration > 15:
        raise SystemExit("--segment-duration must be between 1 and 15 seconds.")
    total = count or math.ceil(duration / segment_duration)
    segments: list[tuple[int, int]] = []
    for index in range(total):
        start = index * segment_duration
        end = min(duration, (index + 1) * segment_duration)
        if start >= duration:
            break
        segments.append((start, end))
    return segments


def api_key_env_args(value: str) -> list[str]:
    names = [item.strip() for item in value.split(",") if item.strip()]
    args: list[str] = []
    for name in names:
        args.extend(["--api-key-env", name])
    return args


def run_command(cmd: list[str], dry_run: bool = False) -> None:
    printable = " ".join(cmd)
    if dry_run:
        print(f"[dry-run] {printable}")
        return
    print(f"[run] {printable}", flush=True)
    subprocess.run(cmd, check=True)


def make_project_dir(output_root: pathlib.Path, project_name: str | None) -> pathlib.Path:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    name = slugify(project_name or f"ad-storyboard-{stamp}")
    project_dir = output_root.expanduser().resolve() / name
    project_dir.mkdir(parents=True, exist_ok=True)
    for sub in ("inputs", "prompts/storyboards", "prompts/videos", "storyboards", "videos", "logs"):
        (project_dir / sub).mkdir(parents=True, exist_ok=True)
    return project_dir


def write_json(path: pathlib.Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_text(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def storyboard_prompt(
    script_text: str,
    product_notes: str,
    duration: int,
    segment: tuple[int, int],
    index: int,
    total: int,
    storyboard_aspect: str,
    storyboard_frames: int,
    language: str,
) -> str:
    start, end = segment
    return f"""
Use case: ads-marketing
Asset type: polished storyboard sheet for an AI video generation workflow
Primary request: Create storyboard sheet {index + 1} of {total} for a {duration}s commercial video. This sheet covers {start}-{end}s only.
Input images: The attached product image(s) are strict product references. Preserve the real product shape, material, label placement, color, scale, and category. Do not invent a new product, fake capacity, fake power number, fake ingredient percentage, or fake brand logo.

Ad script:
{script_text}

Product notes:
{product_notes or "Use the product image as the source of truth."}

Storyboard rules:
- Output a clean {storyboard_aspect} storyboard/planning sheet.
- Include approximately {storyboard_frames} numbered panels for this {start}-{end}s segment.
- Each panel should show a vertical-video composition suitable for final 9:16 video.
- Add concise panel labels: time range, shot size, camera movement, action, and mood.
- Use {language} for storyboard labels unless the ad script explicitly requires another language.
- Keep labels short and readable; do not create dense tables.
- If the script already has exact on-screen text, preserve it. Otherwise avoid inventing claims.

Visual direction:
- Make it production-ready, realistic, and commercial.
- Prioritize product consistency, clear scene progression, and direct usefulness for Seedance video generation.
- No unrelated products, no random logos, no watermark, no fake UI unless the script asks for UI.
- Avoid clear human faces unless the script explicitly requires faces and the source material is safe to use.
""".strip()


def video_prompt(
    script_text: str,
    product_notes: str,
    duration: int,
    segment: tuple[int, int],
    index: int,
    total: int,
) -> str:
    start, end = segment
    segment_len = end - start
    return f"""
{segment_len}秒，9:16竖版，写实商业广告质感。@图片1是已经确认的故事版，请以故事版画面本身作为镜头、动作、构图、节奏和视觉风格的主要依据。不要在提示词中重新拆解或改写逐秒分镜；让模型直接把故事版演绎为全屏真实广告成片。

这是完整{duration}秒广告中的第{index + 1}/{total}段，对应原时间轴{start}-{end}秒。故事版中的面板顺序即为视频顺序；参考其产品外观、场景、肤感、质地、光影、运镜提示和情绪递进，但不要复刻故事版的网格边框、编号、表格、小字、标题、排版UI或水印。

产品约束：
{product_notes or "严格参考故事版左上角产品部分。"}

执行要求：
- 严格保持产品一致，不要变成其他品类或其他包装。
- 画面比例必须为9:16竖版。
- 使用高级商业广告镜头语言：产品特写、质地细节、场景切换、浅景深、干净光影。
- 只使用故事版中已经出现的卖点和表达，不展示虚假参数、虚构认证或额外品牌。
- 避免清晰真人正脸，除非脚本明确需要。
- 字幕和旁白只在用户明确要求时出现；如需字幕/旁白，使用故事版中的key copy，避免新增文案。
- 禁止LOGO、水印和分镜板UI元素。
- 生成与画面匹配的音乐和环境音效；如脚本含旁白，可生成自然旁白，否则以音乐和音效为主。
""".strip()


def load_project(project_dir: pathlib.Path) -> dict[str, Any]:
    path = project_dir / "project.json"
    if not path.exists():
        raise SystemExit(f"project.json not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def command_storyboard(args: argparse.Namespace) -> int:
    script_text = read_script(args)
    product_images = [str(pathlib.Path(p).expanduser().resolve()) for p in args.product_image or []]
    if not product_images:
        raise SystemExit("At least one --product-image is required for storyboards.")
    base_url = args.base_url or "https://api.example.com"
    if not args.dry_run and not args.base_url:
        raise SystemExit(
            "Gateway base URL is required. Run configure_ai_gateway.py, set AI_GATEWAY_BASE_URL, "
            "or pass --base-url."
        )

    segments = split_segments(args.duration, args.segment_duration, args.storyboard_count)
    project_dir = make_project_dir(pathlib.Path(args.output_root), args.project_name)

    script_path = project_dir / "inputs" / "ad_script.txt"
    write_text(script_path, script_text)

    manifest: dict[str, Any] = {
        "skill": "script-to-storyboard-video",
        "stage": "storyboard",
        "project_dir": str(project_dir),
        "duration": args.duration,
        "segment_duration": args.segment_duration,
        "segments": [],
        "product_images": product_images,
        "storyboard_model": args.image_model,
        "storyboard_size": args.storyboard_size,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }

    for index, segment in enumerate(segments):
        start, end = segment
        prompt = storyboard_prompt(
            script_text=script_text,
            product_notes=args.product_notes or "",
            duration=args.duration,
            segment=segment,
            index=index,
            total=len(segments),
            storyboard_aspect=args.storyboard_aspect,
            storyboard_frames=args.storyboard_frames,
            language=args.language,
        )
        prompt_path = project_dir / "prompts" / "storyboards" / f"storyboard_{index + 1:02d}_{start}-{end}s.prompt.txt"
        output_path = project_dir / "storyboards" / f"storyboard_{index + 1:02d}_{start}-{end}s.png"
        json_path = project_dir / "logs" / f"storyboard_{index + 1:02d}_{start}-{end}s.response.json"
        write_text(prompt_path, prompt)

        cmd = [
            sys.executable,
            str(IMAGE_TOOL),
            "edit",
            "--base-url",
            base_url,
            *api_key_env_args(args.api_key_env),
            "--model",
            args.image_model,
            "--prompt-file",
            str(prompt_path),
            "--size",
            args.storyboard_size,
            "--quality",
            args.image_quality,
            "--output",
            str(output_path),
            "--save-json",
            str(json_path),
        ]
        for image in product_images:
            cmd.extend(["--image", image])
        if args.dry_run:
            cmd.append("--dry-run")
        run_command(cmd, dry_run=False)

        manifest["segments"].append({
            "index": index + 1,
            "start": start,
            "end": end,
            "storyboard_prompt": str(prompt_path),
            "storyboard_image": str(output_path),
            "storyboard_response": str(json_path),
        })

    write_json(project_dir / "project.json", manifest)
    print(f"project_dir={project_dir}")
    print("Next: review the storyboard image(s). After approval, run the video stage with --confirmed.")
    return 0


def build_video_job(args: argparse.Namespace, project_dir: pathlib.Path, project: dict[str, Any], segment: dict[str, Any]) -> list[str]:
    script_text = pathlib.Path(project_dir / "inputs" / "ad_script.txt").read_text(encoding="utf-8")
    start = int(segment["start"])
    end = int(segment["end"])
    index = int(segment["index"]) - 1
    total = len(project["segments"])
    prompt = video_prompt(
        script_text=script_text,
        product_notes=args.product_notes or "",
        duration=int(project["duration"]),
        segment=(start, end),
        index=index,
        total=total,
    )
    prompt_path = project_dir / "prompts" / "videos" / f"video_{index + 1:02d}_{start}-{end}s.prompt.txt"
    output_path = project_dir / "videos" / f"video_{index + 1:02d}_{start}-{end}s.mp4"
    json_path = project_dir / "logs" / f"video_{index + 1:02d}_{start}-{end}s.response.json"
    write_text(prompt_path, prompt)

    cmd = [
        sys.executable,
        str(VIDEO_TOOL),
        "--base-url",
        args.base_url,
        *api_key_env_args(args.api_key_env),
        "--model",
        args.video_model,
        "--prompt-file",
        str(prompt_path),
        "--image",
        str(segment["storyboard_image"]),
        "--image-field",
        "image",
        "--duration",
        str(end - start),
        "--width",
        str(args.width),
        "--height",
        str(args.height),
        "--resolution",
        args.resolution,
        "--ratio",
        args.ratio,
        "--output",
        str(output_path),
        "--save-json",
        str(json_path),
        "--initial-delay",
        str(args.initial_delay),
        "--poll-interval",
        str(args.poll_interval),
        "--max-polls",
        str(args.max_polls),
        "--create-timeout",
        str(args.create_timeout),
    ]
    if args.generate_audio:
        cmd.append("--generate-audio")
    else:
        cmd.append("--no-generate-audio")
    if args.watermark:
        cmd.append("--watermark")
    else:
        cmd.append("--no-watermark")
    if args.dry_run:
        cmd.append("--dry-run")
    return cmd


def command_video(args: argparse.Namespace) -> int:
    if not args.confirmed and not args.dry_run:
        raise SystemExit("Refusing to generate video before approval. Re-run with --confirmed after the storyboard is approved.")
    args.base_url = args.base_url or "https://api.example.com"
    if not args.dry_run and not DEFAULT_BASE_URL and args.base_url == "https://api.example.com":
        raise SystemExit(
            "Gateway base URL is required. Run configure_ai_gateway.py, set AI_GATEWAY_BASE_URL, "
            "or pass --base-url."
        )
    project_dir = pathlib.Path(args.project_dir).expanduser().resolve()
    project = load_project(project_dir)
    segments = project.get("segments") or []
    if not segments:
        raise SystemExit("No storyboard segments found in project.json.")

    jobs = [build_video_job(args, project_dir, project, segment) for segment in segments]
    if args.parallel <= 1 or len(jobs) <= 1:
        for cmd in jobs:
            run_command(cmd, dry_run=False)
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.parallel) as executor:
            futures = [executor.submit(run_command, cmd, False) for cmd in jobs]
            for future in concurrent.futures.as_completed(futures):
                future.result()

    project["stage"] = "video"
    project["video_model"] = args.video_model
    project["video_ratio"] = args.ratio
    project["video_resolution"] = args.resolution
    project["generate_audio"] = args.generate_audio
    write_json(project_dir / "project.json", project)
    print(f"project_dir={project_dir}")
    print(f"videos_dir={project_dir / 'videos'}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ad script + product image -> approved storyboard -> vertical video.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    story = subparsers.add_parser("storyboard", help="Generate storyboard sheet(s) from a script and product image(s).")
    story.add_argument("--script")
    story.add_argument("--script-file")
    story.add_argument("--product-image", action="append", required=True)
    story.add_argument("--product-notes")
    story.add_argument("--duration", type=int, required=True)
    story.add_argument("--segment-duration", type=int, default=15)
    story.add_argument("--storyboard-count", type=int)
    story.add_argument("--storyboard-frames", type=int, default=6)
    story.add_argument("--storyboard-aspect", default="16:9")
    story.add_argument("--language", default="Chinese")
    story.add_argument("--project-name")
    story.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    story.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="NewAPI-compatible root URL. Defaults to AI_GATEWAY_BASE_URL, then legacy variables.",
    )
    story.add_argument("--api-key-env", default=DEFAULT_API_KEY_ENVS)
    story.add_argument("--image-model", default=DEFAULT_IMAGE_MODEL)
    story.add_argument("--image-quality", default="high")
    story.add_argument("--storyboard-size", default="2048x1152")
    story.add_argument("--dry-run", action="store_true")
    story.set_defaults(func=command_storyboard)

    video = subparsers.add_parser("video", help="Generate videos from approved storyboard sheet(s).")
    video.add_argument("--project-dir", required=True)
    video.add_argument("--confirmed", action="store_true", help="Required for real video generation after human approval.")
    video.add_argument("--product-notes")
    video.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="NewAPI-compatible root URL. Defaults to AI_GATEWAY_BASE_URL, then legacy variables.",
    )
    video.add_argument("--api-key-env", default=DEFAULT_API_KEY_ENVS)
    video.add_argument("--video-model", default=DEFAULT_VIDEO_MODEL)
    video.add_argument("--ratio", default="9:16")
    video.add_argument("--width", type=int, default=720)
    video.add_argument("--height", type=int, default=1280)
    video.add_argument("--resolution", default="720p")
    video.add_argument("--generate-audio", action=argparse.BooleanOptionalAction, default=True)
    video.add_argument("--watermark", action=argparse.BooleanOptionalAction, default=False)
    video.add_argument("--parallel", type=int, default=2)
    video.add_argument("--initial-delay", type=float, default=8)
    video.add_argument("--poll-interval", type=float, default=15)
    video.add_argument("--max-polls", type=int, default=40)
    video.add_argument("--create-timeout", type=int, default=300)
    video.add_argument("--dry-run", action="store_true")
    video.set_defaults(func=command_video)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
