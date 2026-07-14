#!/usr/bin/env python3
"""Reusable CLI for /v1/video/generations video jobs.

For compatible video gateways, the create payload can mirror duration and
format hints into provider-specific metadata.

Examples:
  export NEWAPI_API_KEY="sk-..."
  python scripts/generate_video.py \
    --model doubao-seedance-2-0-fast-260128 \
    --prompt "A paper boat on a lake at sunrise" \
    --duration 4 \
    --metadata '{"resolution":"480p","ratio":"16:9","generate_audio":false}'

  python scripts/generate_video.py --task-id task_xxx --download

  python scripts/generate_video.py \
    --model veo-3.1-fast-generate-preview \
    --prompt "Animate these product references" \
    --image product-front.png \
    --image product-side.png
"""

from __future__ import annotations

import argparse
import base64
import json
import math
import mimetypes
import os
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request
import uuid
from typing import Any

from env_utils import COMMON_BASE_URL_ENV, load_skill_env, resolve_base_url


load_skill_env()

DONE_STATES = {"completed", "success", "succeeded"}
FAILED_STATES = {"failed", "fail", "error", "expired"}


class ApiError(RuntimeError):
    def __init__(self, status: int | str, body: Any) -> None:
        super().__init__(f"HTTP {status}: {body}")
        self.status = status
        self.body = body


def parse_json_arg(value: str | None, field_name: str) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{field_name} must be valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise SystemExit(f"{field_name} must be a JSON object.")
    return parsed


def read_prompt(args: argparse.Namespace) -> str:
    if args.prompt and args.prompt_file:
        raise SystemExit("Use either --prompt or --prompt-file, not both.")
    if args.prompt_file:
        return pathlib.Path(args.prompt_file).read_text(encoding="utf-8").strip()
    if args.prompt:
        return args.prompt
    if not args.task_id:
        raise SystemExit("--prompt or --prompt-file is required when creating a task.")
    return ""


def looks_like_url(value: str) -> bool:
    return value.startswith(("http://", "https://", "data:"))


def encode_image_reference(value: str, image_encoding: str) -> str:
    if looks_like_url(value):
        return value

    path = pathlib.Path(value)
    if not path.exists():
        raise SystemExit(f"Image file not found: {value}")
    if not path.is_file():
        raise SystemExit(f"Image path is not a file: {value}")

    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    if image_encoding == "base64":
        return encoded

    mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return f"data:{mime_type};base64,{encoded}"


def encode_image_object(value: str) -> dict[str, str]:
    if looks_like_url(value):
        if value.startswith("gs://"):
            return {"gcsUri": value}
        if value.startswith("data:"):
            prefix, encoded = value.split(",", 1)
            mime_type = prefix.split(":", 1)[1].split(";", 1)[0]
            return {"bytesBase64Encoded": encoded, "mimeType": mime_type}
        return {"uri": value}

    path = pathlib.Path(value)
    if not path.exists():
        raise SystemExit(f"Image file not found: {value}")
    if not path.is_file():
        raise SystemExit(f"Image path is not a file: {value}")

    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return {
        "bytesBase64Encoded": encoded,
        "mimeType": mime_type,
    }


def add_images_to_payload(payload: dict[str, Any], args: argparse.Namespace) -> None:
    if not args.images:
        return

    images = [
        encode_image_reference(image, args.image_encoding)
        for image in args.images
    ]
    image_field = args.image_field
    if image_field == "auto":
        image_field = "image" if len(images) == 1 else "images"

    if image_field == "content":
        roles = image_roles(args, len(images))
        content: list[dict[str, Any]] = []
        prompt = payload.pop("prompt") if args.content_only else payload.get("prompt")
        if prompt:
            content.append({"type": "text", "text": prompt})
        for image, role in zip(images, roles):
            content.append({
                "type": "image_url",
                "image_url": {"url": image},
                "role": role,
            })
        payload["content"] = content
        return

    if image_field in {"image", "input_reference"} and len(images) > 1:
        raise SystemExit(
            f"--image-field {image_field} accepts one image. "
            "Use --image-field images/reference_images, or provide one --image."
        )

    payload[image_field] = images[0] if image_field in {"image", "input_reference"} else images


def add_last_frame_to_payload(payload: dict[str, Any], args: argparse.Namespace) -> None:
    if not args.last_frame:
        return
    field_name = args.last_frame_field
    if args.last_frame_encoding == "image-object":
        payload[field_name] = encode_image_object(args.last_frame)
        return
    payload[field_name] = encode_image_reference(args.last_frame, args.last_frame_encoding)


def image_roles(args: argparse.Namespace, count: int) -> list[str]:
    if args.image_roles:
        roles = [role.strip() for role in args.image_roles.split(",") if role.strip()]
    elif count == 1:
        roles = ["first_frame"]
    elif count == 2:
        roles = ["first_frame", "last_frame"]
    else:
        roles = ["reference_image"] * count

    if len(roles) != count:
        raise SystemExit(
            f"--image-roles provided {len(roles)} role(s), but {count} image(s) were provided."
        )
    return roles


def get_api_key(args: argparse.Namespace) -> str:
    if args.api_key:
        return args.api_key
    for env_name in args.api_key_env:
        value = os.getenv(env_name)
        if value:
            return value
    raise SystemExit(
        "API key not found. Set NEWAPI_API_KEY or pass --api-key. "
        "You can also add env names with --api-key-env."
    )


def request_json(
    base_url: str,
    method: str,
    path: str,
    api_key: str,
    payload: dict[str, Any] | None = None,
    timeout: int = 120,
) -> tuple[int, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if method == "POST":
        headers["Idempotency-Key"] = str(uuid.uuid4())

    req = urllib.request.Request(
        base_url.rstrip("/") + path,
        data=body,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode("utf-8", errors="replace")
            return resp.status, parse_response(text)
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        raise ApiError(exc.code, parse_response(text)) from exc
    except urllib.error.URLError as exc:
        raise ApiError("network_error", str(exc)) from exc


def parse_response(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def create_task(args: argparse.Namespace, api_key: str, prompt: str) -> dict[str, Any]:
    payload = build_create_payload(args, prompt)
    _, data = request_json(
        args.base_url,
        "POST",
        "/v1/video/generations",
        api_key,
        payload,
        timeout=args.create_timeout,
    )
    return data


def get_task(args: argparse.Namespace, api_key: str, task_id: str) -> dict[str, Any]:
    _, data = request_json(
        args.base_url,
        "GET",
        f"/v1/video/generations/{task_id}",
        api_key,
        timeout=args.status_timeout,
    )
    return data


def find_task_id(data: Any) -> str | None:
    if not isinstance(data, dict):
        return None
    for key in ("task_id", "id"):
        value = data.get(key)
        if isinstance(value, str) and value:
            return value
    inner = data.get("data")
    if isinstance(inner, dict):
        for key in ("task_id", "id"):
            value = inner.get(key)
            if isinstance(value, str) and value:
                return value
    return None


def unwrap_data(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {}
    inner = data.get("data")
    if isinstance(inner, dict):
        return inner
    return data


def task_summary(data: Any) -> dict[str, Any]:
    outer = unwrap_data(data)
    nested = outer.get("data") if isinstance(outer.get("data"), dict) else {}
    content = nested.get("content") if isinstance(nested.get("content"), dict) else {}

    status = nested.get("status") or outer.get("status") or data.get("status")
    progress = outer.get("progress") or data.get("progress")
    video_url = outer.get("result_url") or content.get("video_url")
    fail_reason = (
        outer.get("fail_reason")
        or nested.get("error")
        or outer.get("error")
        or data.get("message")
    )

    return {
        "status": status,
        "progress": progress,
        "video_url": video_url,
        "fail_reason": fail_reason,
    }


def is_done(status: Any) -> bool:
    return str(status or "").lower() in DONE_STATES


def is_failed(status: Any) -> bool:
    return str(status or "").lower() in FAILED_STATES


def poll_task(args: argparse.Namespace, api_key: str, task_id: str) -> dict[str, Any]:
    last: dict[str, Any] = {}
    for poll_index in range(1, args.max_polls + 1):
        if poll_index == 1:
            time.sleep(args.initial_delay)
        else:
            time.sleep(args.poll_interval)

        last = get_task(args, api_key, task_id)
        summary = task_summary(last)
        print(
            f"poll={poll_index} status={summary['status']} "
            f"progress={summary['progress']}",
            flush=True,
        )

        if is_done(summary["status"]) or is_failed(summary["status"]):
            return last

    raise TimeoutError(f"Task did not finish after {args.max_polls} polls: {task_id}")


def safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_")
    return cleaned or "video"


def default_output_path(args: argparse.Namespace, task_id: str) -> pathlib.Path:
    output_dir = pathlib.Path(args.output_dir)
    stem = safe_filename(f"{args.model or 'video'}_{task_id}")
    return output_dir / f"{stem}.mp4"


def download_file(url: str, output_path: pathlib.Path, timeout: int) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        with output_path.open("wb") as fh:
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                fh.write(chunk)
    return output_path.stat().st_size


def download_task_content(
    base_url: str,
    api_key: str,
    task_id: str,
    output_path: pathlib.Path,
    timeout: int,
) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(
        base_url.rstrip("/") + f"/v1/videos/{task_id}/content",
        headers={"Authorization": f"Bearer {api_key}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            with output_path.open("wb") as fh:
                while True:
                    chunk = resp.read(1024 * 1024)
                    if not chunk:
                        break
                    fh.write(chunk)
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        raise ApiError(exc.code, parse_response(text)) from exc
    except urllib.error.URLError as exc:
        raise ApiError("network_error", str(exc)) from exc
    return output_path.stat().st_size


def save_json(path: str | None, data: Any) -> None:
    if not path:
        return
    output_path = pathlib.Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def redact_large_values(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: redact_large_values(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_large_values(item) for item in value]
    if isinstance(value, str) and (
        value.startswith("data:") or len(value) > 500
    ):
        return f"{value[:80]}...<redacted {len(value)} chars>"
    return value


def is_newapi_compat_model(model: str) -> bool:
    model_lower = model.lower()
    return "seedance" in model_lower or "veo" in model_lower


def is_veo_model(model: str) -> bool:
    return "veo" in model.lower()


def infer_ratio(width: int | None, height: int | None) -> str | None:
    if not width or not height:
        return None
    divisor = math.gcd(width, height)
    return f"{width // divisor}:{height // divisor}"


def infer_resolution(width: int | None, height: int | None) -> str | None:
    if not width or not height:
        return None
    return f"{min(width, height)}p"


def apply_newapi_video_compat(payload: dict[str, Any], args: argparse.Namespace) -> None:
    """Mirror video fields for New API task adaptors with provider-specific names."""
    if not is_newapi_compat_model(args.model):
        return

    metadata = payload.get("metadata")
    if metadata is None:
        metadata = {}
        payload["metadata"] = metadata
    if not isinstance(metadata, dict):
        return

    duration = payload.get("duration", args.duration)
    if isinstance(duration, int) and duration > 0:
        payload.setdefault("seconds", str(duration))
        metadata.setdefault("duration", duration)
        if is_veo_model(args.model):
            metadata.setdefault("durationSeconds", duration)

    for key in (
        "content",
        "generate_audio",
        "watermark",
        "seed",
        "ratio",
        "resolution",
    ):
        if key in payload:
            metadata.setdefault(key, payload[key])

    inferred_ratio = infer_ratio(args.width, args.height)
    if inferred_ratio:
        metadata.setdefault("ratio", inferred_ratio)
        if is_veo_model(args.model):
            metadata.setdefault("aspectRatio", inferred_ratio)

    inferred_resolution = infer_resolution(args.width, args.height)
    if inferred_resolution:
        metadata.setdefault("resolution", inferred_resolution)


def build_create_payload(args: argparse.Namespace, prompt: str) -> dict[str, Any]:
    metadata = parse_json_arg(args.metadata, "--metadata")
    extra = parse_json_arg(args.extra, "--extra")

    payload: dict[str, Any] = {
        "model": args.model,
        "prompt": prompt,
        "n": args.n,
    }
    if args.duration is not None:
        payload["duration"] = args.duration
    optional: dict[str, Any] = {
        "generate_audio": args.generate_audio,
        "watermark": args.watermark,
        "seed": args.seed,
        "width": args.width,
        "height": args.height,
    }
    if not (args.width is not None and args.height is not None):
        optional["ratio"] = args.ratio
        optional["resolution"] = args.resolution
    for key, value in optional.items():
        if value is not None:
            payload[key] = value
    if metadata:
        payload["metadata"] = metadata
    add_images_to_payload(payload, args)
    add_last_frame_to_payload(payload, args)
    payload.update(extra)
    apply_newapi_video_compat(payload, args)
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create, poll, and download videos from /v1/video/generations.",
    )
    parser.add_argument(
        "--base-url",
        help="OpenAI-compatible root URL. Defaults to AD_STORYBOARD_BASE_URL or VIDEO_API_BASE_URL.",
    )
    parser.add_argument(
        "--api-key-env",
        action="append",
        default=["NEWAPI_API_KEY", "PRODUCT_UGC_VIDEO_API_KEY", "VIDEO_API_KEY"],
        help="Environment variable to read the API key from. Can be repeated.",
    )
    parser.add_argument("--api-key", help="API key. Prefer env vars for shell history safety.")
    parser.add_argument("--model", default=os.getenv("AD_STORYBOARD_VIDEO_MODEL", "seedance-model-id"))
    parser.add_argument("--prompt")
    parser.add_argument("--prompt-file")
    parser.add_argument("--task-id", help="Skip creation and query an existing task.")
    parser.add_argument("--duration", type=int, default=4)
    parser.add_argument("--n", type=int, default=1)
    parser.add_argument("--ratio", default="16:9", help="Top-level video aspect ratio, for example 16:9, 4:3, 9:16.")
    parser.add_argument("--resolution", default="480p", help="Top-level output resolution, for example 480p or 720p.")
    parser.add_argument("--generate-audio", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--watermark", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--width", type=int, help="Top-level video width, useful for model-specific format inference.")
    parser.add_argument("--height", type=int, help="Top-level video height, useful for model-specific format inference.")
    parser.add_argument(
        "--image",
        dest="images",
        action="append",
        help="Reference image path, URL, or data URL. Repeat for multiple images.",
    )
    parser.add_argument(
        "--image-field",
        default="auto",
        help=(
            "Payload field for images. auto uses image for one image and images for "
            "multiple images. Use content to send role-tagged image_url items. "
            "Common alternatives: input_reference, reference_images."
        ),
    )
    parser.add_argument(
        "--image-roles",
        help=(
            "Comma-separated roles when --image-field content is used. Defaults to "
            "first_frame for one image, first_frame,last_frame for two images."
        ),
    )
    parser.add_argument(
        "--content-only",
        action="store_true",
        help="With --image-field content, move prompt into content and omit top-level prompt.",
    )
    parser.add_argument(
        "--image-encoding",
        choices=["data-url", "base64"],
        default="data-url",
        help="How local image files are encoded before sending.",
    )
    parser.add_argument(
        "--last-frame",
        help="Explicit last-frame image for models that support first/last frame interpolation.",
    )
    parser.add_argument(
        "--last-frame-field",
        default="lastFrame",
        help="Payload field name for the explicit last frame. Defaults to lastFrame.",
    )
    parser.add_argument(
        "--last-frame-encoding",
        choices=["data-url", "base64", "image-object"],
        default="image-object",
        help="How the explicit last frame is encoded before sending.",
    )
    parser.add_argument(
        "--metadata",
        help=(
            "Optional JSON object sent as payload.metadata. For New API Veo/Seedance "
            "models, duration and width/height format hints are mirrored here automatically."
        ),
    )
    parser.add_argument(
        "--extra",
        help="JSON object merged into the top-level create payload.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print the create payload and exit.")
    parser.add_argument("--no-wait", action="store_true", help="Only create the task.")
    parser.add_argument("--download", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--output", help="Video output path. Defaults to outputs/<model>_<task>.mp4.")
    parser.add_argument("--output-dir", default="outputs")
    parser.add_argument("--save-json", help="Save final API response JSON to this path.")
    parser.add_argument("--initial-delay", type=float, default=2.0)
    parser.add_argument("--poll-interval", type=float, default=8.0)
    parser.add_argument("--max-polls", type=int, default=60)
    parser.add_argument("--create-timeout", type=int, default=180)
    parser.add_argument("--status-timeout", type=int, default=60)
    parser.add_argument("--download-timeout", type=int, default=240)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    prompt = read_prompt(args)
    if not (args.dry_run and not args.task_id):
        args.base_url = resolve_base_url(args.base_url, (COMMON_BASE_URL_ENV, "VIDEO_API_BASE_URL"))

    if args.dry_run and not args.task_id:
        payload = build_create_payload(args, prompt)
        print(json.dumps(redact_large_values(payload), ensure_ascii=False, indent=2))
        return 0

    api_key = get_api_key(args)

    try:
        if args.task_id:
            task_id = args.task_id
            create_response = None
            final_response = get_task(args, api_key, task_id)
        else:
            create_response = create_task(args, api_key, prompt)
            print("create_response=")
            print(json.dumps(create_response, ensure_ascii=False, indent=2))
            task_id = find_task_id(create_response)
            if not task_id:
                raise RuntimeError(f"Create response did not include a task id: {create_response}")
            print(f"task_id={task_id}", flush=True)
            final_response = create_response

        if not args.no_wait:
            final_response = poll_task(args, api_key, task_id)

        summary = task_summary(final_response)
        print("final_summary=")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        save_json(args.save_json, final_response)

        if is_failed(summary["status"]):
            print(json.dumps(final_response, ensure_ascii=False, indent=2), file=sys.stderr)
            return 2

        if args.download and summary["video_url"]:
            output_path = pathlib.Path(args.output) if args.output else default_output_path(args, task_id)
            bytes_written = download_file(
                summary["video_url"],
                output_path,
                timeout=args.download_timeout,
            )
            print(f"saved={output_path.resolve()}")
            print(f"bytes={bytes_written}")
        elif args.download and is_done(summary["status"]):
            output_path = pathlib.Path(args.output) if args.output else default_output_path(args, task_id)
            bytes_written = download_task_content(
                args.base_url,
                api_key,
                task_id,
                output_path,
                timeout=args.download_timeout,
            )
            print(f"saved={output_path.resolve()}")
            print(f"bytes={bytes_written}")
        elif args.download:
            print("No video URL found yet; run again with --task-id to query later.")

        return 0
    except ApiError as exc:
        print("api_error=", file=sys.stderr)
        print(json.dumps({"status": exc.status, "body": exc.body}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"error={type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
