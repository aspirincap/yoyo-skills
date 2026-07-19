#!/usr/bin/env python3
"""Reusable CLI for OpenAI-format image generation and editing.

Examples:
  export AI_GATEWAY_API_KEY="..."

  python scripts/image_tool.py generate \
    --model gpt-image-2 \
    --prompt "A clean ecommerce product photo of a pale blue athletic shirt" \
    --output outputs/images/generated.png

  python scripts/image_tool.py edit \
    --model gpt-image-2 \
    --image outputs/images/generated.png \
    --prompt "Make the shirt coral orange while preserving the composition" \
    --output outputs/images/edited.png

  python scripts/image_tool.py generate \
    --model gemini-3.1-flash-image-preview \
    --prompt "Generate an ecommerce product image" \
    --output outputs/images/gemini.png
"""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import pathlib
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from ai_gateway import gateway_base_url, gateway_model, get_first_setting


SKILL_DIR = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_BASE_URL = gateway_base_url(
    "AD_STORYBOARD_BASE_URL",
    "UGC_IMAGE_BASE_URL",
    "IMAGE_API_BASE_URL",
    "UGC_API_BASE_URL",
    skill_dir=SKILL_DIR,
)
DEFAULT_MODEL = gateway_model(
    "image",
    "AD_STORYBOARD_IMAGE_MODEL",
    "UGC_IMAGE_MODEL",
    default="gpt-image-1",
    skill_dir=SKILL_DIR,
)
DATA_URL_RE = re.compile(r"data:image/(png|jpeg|jpg|webp);base64,([A-Za-z0-9+/=]+)")
MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024
PROTECTED_EXTRA_FIELDS = {"model", "prompt", "messages", "modalities", "n", "size", "image", "mask"}


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


def safe_extra(value: str | None) -> dict[str, Any]:
    extra = parse_json_arg(value, "--extra")
    protected = sorted(PROTECTED_EXTRA_FIELDS.intersection(extra))
    if protected:
        raise SystemExit("--extra cannot override core request fields: " + ", ".join(protected))
    return extra


def read_prompt(args: argparse.Namespace) -> str:
    if args.prompt and args.prompt_file:
        raise SystemExit("Use either --prompt or --prompt-file, not both.")
    if args.prompt_file:
        return pathlib.Path(args.prompt_file).read_text(encoding="utf-8").strip()
    if args.prompt:
        return args.prompt
    raise SystemExit("--prompt or --prompt-file is required.")


def get_api_key(args: argparse.Namespace) -> str:
    if args.api_key:
        return args.api_key
    value = get_first_setting(args.api_key_env, skill_dir=SKILL_DIR)
    if value:
        return value
    raise SystemExit(
        "API key not found. Run configure_ai_gateway.py, set AI_GATEWAY_API_KEY, or pass --api-key. "
        "You can also add env names with --api-key-env."
    )


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
    timeout: int,
) -> dict[str, Any]:
    req = urllib.request.Request(
        base_url.rstrip("/") + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Idempotency-Key": str(uuid.uuid4()),
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


def request_multipart(
    base_url: str,
    path: str,
    api_key: str,
    fields: dict[str, str],
    files: list[tuple[str, pathlib.Path]],
    timeout: int,
) -> dict[str, Any]:
    boundary = f"----image-tool-{uuid.uuid4().hex}"
    body = build_multipart_body(boundary, fields, files)
    req = urllib.request.Request(
        base_url.rstrip("/") + path,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Idempotency-Key": str(uuid.uuid4()),
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


def build_multipart_body(
    boundary: str,
    fields: dict[str, str],
    files: list[tuple[str, pathlib.Path]],
) -> bytes:
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.extend([
            f"--{boundary}\r\n".encode("utf-8"),
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"),
            str(value).encode("utf-8"),
            b"\r\n",
        ])

    for field_name, path in files:
        if not path.exists():
            raise SystemExit(f"Image file not found: {path}")
        if not path.is_file():
            raise SystemExit(f"Image path is not a file: {path}")
        mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        chunks.extend([
            f"--{boundary}\r\n".encode("utf-8"),
            (
                f'Content-Disposition: form-data; name="{field_name}"; '
                f'filename="{path.name}"\r\n'
            ).encode("utf-8"),
            f"Content-Type: {mime_type}\r\n\r\n".encode("utf-8"),
            path.read_bytes(),
            b"\r\n",
        ])

    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(chunks)


def build_generate_payload(args: argparse.Namespace, prompt: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": args.model,
        "prompt": prompt,
        "n": args.n,
        "size": args.size,
    }
    optional = {
        "quality": args.quality,
        "background": args.background,
        "output_format": args.output_format,
        "moderation": args.moderation,
        "style": args.style,
        "user": args.user,
    }
    for key, value in optional.items():
        if value is not None:
            payload[key] = value
    payload.update(safe_extra(args.extra))
    return payload


def build_chat_payload(args: argparse.Namespace, prompt: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": args.model,
        "messages": [{"role": "user", "content": prompt}],
        "modalities": ["text", "image"],
    }
    if args.n != 1:
        payload["n"] = args.n
    if args.user:
        payload["user"] = args.user
    payload.update(safe_extra(args.extra))
    return payload


def build_edit_fields(args: argparse.Namespace, prompt: str) -> dict[str, str]:
    fields: dict[str, str] = {
        "model": args.model,
        "prompt": prompt,
        "n": str(args.n),
        "size": args.size,
    }
    optional = {
        "quality": args.quality,
        "background": args.background,
        "output_format": args.output_format,
        "user": args.user,
    }
    for key, value in optional.items():
        if value is not None:
            fields[key] = str(value)
    for key, value in safe_extra(args.extra).items():
        fields[key] = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
    return fields


def redact_large_values(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: redact_large_values(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_large_values(item) for item in value]
    if isinstance(value, str):
        value = DATA_URL_RE.sub(
            lambda match: match.group(0)[:80] + f"...<redacted {len(match.group(0))} chars>",
            value,
        )
        if len(value) > 500:
            return f"{value[:80]}...<redacted {len(value)} chars>"
    return value


def save_response_json(path: str | None, response: dict[str, Any]) -> None:
    if not path:
        return
    output_path = pathlib.Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(response, ensure_ascii=False, indent=2), encoding="utf-8")


def default_output_path(args: argparse.Namespace, index: int, image_format: str) -> pathlib.Path:
    if args.output:
        output = pathlib.Path(args.output)
        if args.n == 1:
            return output
        stem = output.stem
        suffix = output.suffix or f".{image_format}"
        return output.with_name(f"{stem}_{index + 1}{suffix}")

    output_dir = pathlib.Path(args.output_dir)
    timestamp = int(time.time())
    return output_dir / f"{args.command}_{args.model}_{timestamp}_{index + 1}.{image_format}"


def extract_image_format(response: dict[str, Any], fallback: str = "png") -> str:
    image_format = str(response.get("output_format") or fallback).lower()
    if image_format == "jpeg":
        return "jpg"
    return image_format


def is_gemini_image_model(model: str) -> bool:
    model_lower = model.lower()
    return "gemini" in model_lower and "image" in model_lower


def resolve_endpoint(args: argparse.Namespace) -> str:
    if args.endpoint != "auto":
        return args.endpoint
    if args.command == "generate" and is_gemini_image_model(args.model):
        return "chat"
    return "images"


def download_image(url: str, timeout: int) -> bytes:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise RuntimeError("Image download URLs must use HTTPS.")
    with urllib.request.urlopen(url, timeout=timeout) as response:
        final_url = response.geturl()
        if urllib.parse.urlparse(final_url).scheme != "https":
            raise RuntimeError("Image download redirects must remain on HTTPS.")
        content_type = response.headers.get_content_type()
        if not content_type.startswith("image/"):
            raise RuntimeError(f"Image download returned non-image content type: {content_type}")
        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > MAX_DOWNLOAD_BYTES:
            raise RuntimeError("Image download exceeds the 50 MiB limit.")
        payload = response.read(MAX_DOWNLOAD_BYTES + 1)
        if len(payload) > MAX_DOWNLOAD_BYTES:
            raise RuntimeError("Image download exceeds the 50 MiB limit.")
        return payload


def save_images(args: argparse.Namespace, response: dict[str, Any]) -> list[pathlib.Path]:
    chat_saved = save_chat_images(args, response)
    if chat_saved:
        return chat_saved

    items = response.get("data")
    if not isinstance(items, list) or not items:
        raise RuntimeError(f"Response did not contain image data: {response}")

    image_format = extract_image_format(response)
    saved: list[pathlib.Path] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        output_path = default_output_path(args, index, image_format)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if item.get("b64_json"):
            output_path.write_bytes(base64.b64decode(item["b64_json"]))
        elif item.get("url"):
            output_path.write_bytes(download_image(item["url"], args.download_timeout))
        else:
            raise RuntimeError(f"Image item has neither b64_json nor url: {item}")

        saved.append(output_path.resolve())
    return saved


def save_chat_images(args: argparse.Namespace, response: dict[str, Any]) -> list[pathlib.Path]:
    contents: list[str] = []
    for choice in response.get("choices", []) or []:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message")
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if isinstance(content, str):
            contents.append(content)
        elif isinstance(content, list):
            for part in content:
                if not isinstance(part, dict):
                    continue
                text = part.get("text")
                if isinstance(text, str):
                    contents.append(text)
                image_url = part.get("image_url")
                if isinstance(image_url, dict) and isinstance(image_url.get("url"), str):
                    contents.append(image_url["url"])

    matches: list[tuple[str, str]] = []
    for content in contents:
        matches.extend(DATA_URL_RE.findall(content))
    if not matches:
        return []

    saved: list[pathlib.Path] = []
    for index, (image_format, encoded) in enumerate(matches):
        ext = "jpg" if image_format in {"jpeg", "jpg"} else image_format
        output_path = default_output_path(args, index, ext)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(base64.b64decode(encoded))
        saved.append(output_path.resolve())
    return saved


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="NewAPI-compatible root URL. Defaults to AI_GATEWAY_BASE_URL, then legacy variables.",
    )
    parser.add_argument(
        "--api-key-env",
        action="append",
        default=[
            "AI_GATEWAY_API_KEY",
            "AD_STORYBOARD_API_KEY",
            "UGC_IMAGE_API_KEY",
            "IMAGE_API_KEY",
            "UGC_API_KEY",
            "NEWAPI_API_KEY",
            "OPENAI_API_KEY",
            "PRODUCT_UGC_IMAGE_API_KEY",
        ],
        help="Environment variable to read the API key from. Can be repeated.",
    )
    parser.add_argument("--api-key", help="API key. Prefer env vars for shell history safety.")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--prompt")
    parser.add_argument("--prompt-file")
    parser.add_argument("--n", type=int, default=1)
    parser.add_argument("--size", default="1024x1024")
    parser.add_argument("--quality")
    parser.add_argument("--background")
    parser.add_argument("--output-format")
    parser.add_argument("--user")
    parser.add_argument("--extra", help="JSON object merged into the request.")
    parser.add_argument(
        "--endpoint",
        choices=["auto", "images", "chat"],
        default="auto",
        help="auto routes Gemini image models through /v1/chat/completions.",
    )
    parser.add_argument("--output")
    parser.add_argument("--output-dir", default="outputs/images")
    parser.add_argument("--save-json")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--download-timeout", type=int, default=180)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate and edit images with OpenAI-format image APIs.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate", help="Create images from a prompt.")
    add_common_args(generate)
    generate.add_argument("--moderation")
    generate.add_argument("--style")

    edit = subparsers.add_parser("edit", help="Edit or extend images from an input image.")
    add_common_args(edit)
    edit.add_argument("--image", required=True, action="append", help="Input image file. Repeat if supported.")
    edit.add_argument("--mask", help="Optional mask image file.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    prompt = read_prompt(args)
    if not args.dry_run and not args.base_url:
        raise SystemExit(
            "Image base URL is required. Run configure_ai_gateway.py, set AI_GATEWAY_BASE_URL, "
            "or pass --base-url."
        )

    try:
        if args.command == "generate":
            endpoint = resolve_endpoint(args)
            payload = build_chat_payload(args, prompt) if endpoint == "chat" else build_generate_payload(args, prompt)
            if args.dry_run:
                print(json.dumps({"endpoint": endpoint, "payload": payload}, ensure_ascii=False, indent=2))
                return 0
            path = "/v1/chat/completions" if endpoint == "chat" else "/v1/images/generations"
            response = request_json(
                args.base_url,
                path,
                get_api_key(args),
                payload,
                timeout=args.timeout,
            )
        elif args.command == "edit":
            fields = build_edit_fields(args, prompt)
            files = [("image", pathlib.Path(image)) for image in args.image]
            if args.mask:
                files.append(("mask", pathlib.Path(args.mask)))
            if args.dry_run:
                print(json.dumps({"fields": fields, "files": [(name, str(path)) for name, path in files]}, ensure_ascii=False, indent=2))
                return 0
            response = request_multipart(
                args.base_url,
                "/v1/images/edits",
                get_api_key(args),
                fields,
                files,
                timeout=args.timeout,
            )
        else:
            raise RuntimeError(f"Unknown command: {args.command}")

        preview = redact_large_values(response)
        print("response=")
        print(json.dumps(preview, ensure_ascii=False, indent=2))
        save_response_json(args.save_json, response)
        saved_paths = save_images(args, response)
        if not saved_paths:
            raise RuntimeError("The image API returned no saved image artifacts.")
        for path in saved_paths:
            print(f"saved={path}")
            print(f"bytes={path.stat().st_size}")
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
