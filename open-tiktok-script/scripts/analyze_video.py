#!/usr/bin/env python3
"""Analyze local TikTok videos through a user-configured Gemini-compatible endpoint."""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
from pathlib import Path
import sys
from typing import Any
from urllib import error, request


DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com"
DEFAULT_MODEL = "gemini-2.5-flash"
DEFAULT_MAX_INLINE_MB = 20
SKILL_DIR = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = SKILL_DIR / ".env"
API_KEY_ENV_VARS = (
    "GEMINI_VIDEO_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "NEWAPI_API_KEY",
)
MODEL_ALIASES = {
    "flash": DEFAULT_MODEL,
}


def is_placeholder_value(value: str) -> bool:
    normalized = value.strip().lower()
    return normalized in {"placeholder", "changeme", "your_key", "your-key"} or "replace_with" in normalized


def local_env_file() -> Path:
    return DEFAULT_ENV_FILE


def load_local_config() -> dict[str, str]:
    path = local_env_file()
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and value and not is_placeholder_value(value):
            values[key] = value
    return values


LOCAL_CONFIG = load_local_config()


def setting(name: str, default: str | None = None) -> str | None:
    return os.getenv(name) or LOCAL_CONFIG.get(name) or default


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze a local TikTok video with Gemini inlineData through a configured compatible endpoint."
    )
    parser.add_argument("--video", "-v", required=True, help="Local media/video path. URLs are not supported.")
    prompt_group = parser.add_mutually_exclusive_group(required=True)
    prompt_group.add_argument("--prompt", "-p", help="Analysis prompt sent after the video part.")
    prompt_group.add_argument("--prompt-file", help="Read the prompt from a UTF-8 text file.")
    parser.add_argument("--output", "-o", help="Save output to this file.")
    parser.add_argument("--raw-response", action="store_true", help="Write/print the full JSON response.")
    parser.add_argument("--mime-type", help="Override inferred local media MIME type.")
    parser.add_argument(
        "--base-url",
        default=setting("GEMINI_VIDEO_BASE_URL", DEFAULT_BASE_URL),
        help=f"API base URL. Default: {DEFAULT_BASE_URL}",
    )
    parser.add_argument(
        "--model",
        "-m",
        default=setting("GEMINI_VIDEO_MODEL", DEFAULT_MODEL),
        help=(
            "Gemini model or compatibility alias. "
            f"'flash' maps to {DEFAULT_MODEL}. Default: {DEFAULT_MODEL}"
        ),
    )
    parser.add_argument(
        "--resolution",
        "-r",
        choices=("low", "medium", "high"),
        default="medium",
        help="Compatibility alias for --media-resolution. Default: medium.",
    )
    parser.add_argument(
        "--media-resolution",
        choices=("low", "medium", "high"),
        help="Optional media resolution hint sent in generation_config.",
    )
    parser.add_argument("--start", type=int, help="Compatibility alias: start time in seconds.")
    parser.add_argument("--end", type=int, help="Compatibility alias: end time in seconds.")
    parser.add_argument("--start-offset", help="Optional clip start, for example 40s.")
    parser.add_argument("--end-offset", help="Optional clip end, for example 80s.")
    parser.add_argument("--fps", type=float, help="Optional video frame sampling rate.")
    parser.add_argument(
        "--api-key-env",
        default=",".join(API_KEY_ENV_VARS),
        help="Comma-separated environment variable names to check for the API key.",
    )
    parser.add_argument(
        "--auth-mode",
        choices=("both", "x-goog", "bearer"),
        default=setting("GEMINI_VIDEO_AUTH_MODE", "x-goog"),
        help="Authentication header mode. Default: x-goog.",
    )
    parser.add_argument(
        "--max-inline-mb",
        "--inline-limit-mb",
        dest="max_inline_mb",
        type=float,
        default=float(setting("GEMINI_VIDEO_MAX_INLINE_MB", str(DEFAULT_MAX_INLINE_MB))),
        help="Safety limit for local inline base64 media size in MB. Default: 20.",
    )
    parser.add_argument(
        "--allow-large-inline",
        action="store_true",
        help="Send files larger than --max-inline-mb anyway. The gateway may reject large payloads.",
    )
    parser.add_argument("--timeout", type=int, default=300, help="HTTP timeout in seconds.")
    return parser.parse_args()


def normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def normalize_model(model: str) -> str:
    if model == "pro":
        configured = setting("GEMINI_VIDEO_PRO_MODEL")
        if configured:
            return configured
        raise SystemExit(
            "--model pro is a legacy alias and no GEMINI_VIDEO_PRO_MODEL is configured. "
            f"Use --model flash / {DEFAULT_MODEL}, or set GEMINI_VIDEO_PRO_MODEL to a model available on the gateway."
        )
    return MODEL_ALIASES.get(model, model)


def get_api_key(names_csv: str) -> str:
    names = [item.strip() for item in names_csv.split(",") if item.strip()]
    for name in names:
        value = os.getenv(name) or LOCAL_CONFIG.get(name)
        if value:
            return value
    raise SystemExit(f"Missing API key. Set one of {', '.join(names)} in the shell or {local_env_file()}")


def is_url(value: str) -> bool:
    return value.startswith("http://") or value.startswith("https://")


def infer_mime_type(path: Path, override: str | None) -> str:
    if override:
        return override
    mime_type, _ = mimetypes.guess_type(str(path))
    return mime_type or "video/mp4"


def auth_headers(api_key: str, auth_mode: str) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if auth_mode in ("both", "x-goog"):
        headers["x-goog-api-key"] = api_key
    if auth_mode in ("both", "bearer"):
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def read_error_body(exc: error.HTTPError) -> str:
    try:
        return exc.read().decode("utf-8", errors="replace")
    except Exception:
        return ""


def diagnose_http_error(status: int, url: str, body: str) -> str:
    lower = body.lower()
    suggestions: list[str] = []
    if status in (401, 403) or "unauthorized" in lower or "permission" in lower:
        suggestions.append("verify the API key, auth mode, model permission, and gateway account quota")
    if status == 404 or "not found" in lower or ("model" in lower and "not" in lower):
        suggestions.append("verify the model name and endpoint path for this gateway")
    if status == 413 or "too large" in lower or "payload" in lower or "exceed" in lower:
        suggestions.append("trim or compress the video below about 20 MB before analysis")
    if "mime" in lower or "media type" in lower or "unsupported" in lower:
        suggestions.append("check that --mime-type matches the actual file, for example video/mp4")
    if "file_uri" in lower or "file api" in lower or "filedata" in lower:
        suggestions.append("use local inlineData only; this relay does not support File API or fileData.fileUri")
    if not suggestions:
        suggestions.append("rerun with --raw-response and check gateway/provider details")
    next_steps = "\n".join(f"- Next step: {item}." for item in suggestions)
    return f"HTTP {status} from Gemini endpoint: {url}\n{body}\n{next_steps}"


def post_json(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: int) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=data, headers=headers, method="POST")
    try:
        with request.urlopen(req, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except error.HTTPError as exc:
        body = read_error_body(exc)
        raise SystemExit(diagnose_http_error(exc.code, url, body)) from exc
    except error.URLError as exc:
        raise SystemExit(
            f"Request failed for Gemini endpoint: {url}\n"
            f"- Next step: check network, DNS, proxy, or base URL.\n{exc}"
        ) from exc
    return json.loads(body) if body else {}


def local_media_path(video: str) -> Path:
    if is_url(video):
        raise SystemExit(
            "Remote URLs, YouTube URLs, file URIs, and Gemini File API uploads are not supported here. "
            "Download the TikTok video first and pass a local file path."
        )
    path = Path(video).expanduser().resolve()
    if not path.exists():
        raise SystemExit(f"Media file not found: {path}")
    if not path.is_file():
        raise SystemExit(f"Media path is not a file: {path}")
    return path


def offset(value: str | None, seconds: int | None) -> str | None:
    if value:
        return value
    if seconds is not None:
        return f"{seconds}s"
    return None


def video_metadata(args: argparse.Namespace) -> dict[str, Any] | None:
    metadata: dict[str, Any] = {}
    start_offset = offset(args.start_offset, args.start)
    end_offset = offset(args.end_offset, args.end)
    if start_offset:
        metadata["start_offset"] = start_offset
    if end_offset:
        metadata["end_offset"] = end_offset
    if args.fps is not None:
        metadata["fps"] = args.fps
    return metadata or None


def local_media_part(args: argparse.Namespace, path: Path) -> dict[str, Any]:
    mime_type = infer_mime_type(path, args.mime_type)
    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb > args.max_inline_mb and not args.allow_large_inline:
        raise SystemExit(
            f"Media file is {size_mb:.1f} MB, above --max-inline-mb={args.max_inline_mb:.1f}. "
            "This analyzer is configured for inline local media payloads, not File API uploads. "
            "Trim, split, or compress the TikTok clip before analysis."
        )
    part: dict[str, Any] = {
        "inline_data": {
            "mime_type": mime_type,
            "data": base64.b64encode(path.read_bytes()).decode("ascii"),
        }
    }
    metadata = video_metadata(args)
    if metadata:
        part["video_metadata"] = metadata
    return part


def analysis_prompt(args: argparse.Namespace) -> str:
    if args.prompt_file:
        return Path(args.prompt_file).expanduser().read_text(encoding="utf-8")
    return args.prompt


def build_payload(args: argparse.Namespace, media_part: dict[str, Any], prompt: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    media_part,
                    {"text": prompt},
                ],
            }
        ]
    }
    media_resolution = args.media_resolution or args.resolution
    if media_resolution:
        payload["generation_config"] = {"media_resolution": media_resolution}
    return payload


def extract_text(response: dict[str, Any]) -> str:
    texts: list[str] = []
    for candidate in response.get("candidates", []):
        content = candidate.get("content", {})
        for part in content.get("parts", []):
            text = part.get("text")
            if text:
                texts.append(text)
    if texts:
        return "\n\n".join(texts)
    return json.dumps(response, ensure_ascii=False, indent=2)


def main() -> int:
    args = parse_args()
    path = local_media_path(args.video)
    prompt = analysis_prompt(args)
    model = normalize_model(args.model)
    base_url = normalize_base_url(args.base_url)
    endpoint = f"{base_url}/v1beta/models/{model}:generateContent"
    payload = build_payload(args, local_media_part(args, path), prompt)
    response = post_json(
        endpoint,
        payload,
        auth_headers(get_api_key(args.api_key_env), args.auth_mode),
        args.timeout,
    )
    output = json.dumps(response, ensure_ascii=False, indent=2) if args.raw_response else extract_text(response)
    if args.output:
        output_path = Path(args.output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output if output.endswith("\n") else output + "\n", encoding="utf-8")
        print(f"Result saved to: {output_path}", file=sys.stderr)
    else:
        sys.stdout.write(output)
        if not output.endswith("\n"):
            sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
