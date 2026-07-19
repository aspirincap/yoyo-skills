#!/usr/bin/env python3
"""Preflight a NewAPI-compatible image backend without generating an image."""

from __future__ import annotations

import argparse
import json
import pathlib
import urllib.error
import urllib.request
from typing import Any

from ai_gateway import gateway_api_key, gateway_base_url, gateway_model, get_setting


SKILL_DIR = pathlib.Path(__file__).resolve().parents[1]
PORTABLE_SIZES = ("1024x1024", "1024x1536", "1536x1024")


def csv_values(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def request_json(base_url: str, path: str, api_key: str, method: str, timeout: int) -> tuple[int, Any]:
    request = urllib.request.Request(
        base_url.rstrip("/") + path,
        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            try:
                payload: Any = json.loads(body) if body else None
            except json.JSONDecodeError:
                payload = body[:500]
            return response.status, payload
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(body) if body else None
        except json.JSONDecodeError:
            payload = body[:500]
        return exc.code, payload


def model_ids(payload: Any) -> set[str]:
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        return set()
    return {
        str(item["id"])
        for item in payload["data"]
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }


def operation_path(operation: str, endpoint: str, model: str) -> str:
    if operation == "edit":
        return "/v1/images/edits"
    resolved = endpoint
    if resolved == "auto":
        resolved = "chat" if "gemini" in model.lower() and "image" in model.lower() else "images"
    return "/v1/chat/completions" if resolved == "chat" else "/v1/images/generations"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check gateway configuration, model visibility, endpoints and sizes.")
    parser.add_argument("--base-url", default=gateway_base_url("IMAGE_API_BASE_URL", skill_dir=SKILL_DIR))
    parser.add_argument("--api-key", help="Prefer AI_GATEWAY_API_KEY or the shared config file.")
    parser.add_argument("--model", default=gateway_model("image", "IMAGE_MODEL", default=None, skill_dir=SKILL_DIR))
    parser.add_argument("--endpoint", choices=["auto", "images", "chat"], default="auto")
    parser.add_argument("--operation", action="append", choices=["generate", "edit"], default=[])
    parser.add_argument("--size", action="append", default=[])
    parser.add_argument(
        "--supported-sizes",
        default=get_setting(
            "AI_IMAGE_SUPPORTED_SIZES",
            default=",".join(PORTABLE_SIZES),
            skill_dir=SKILL_DIR,
        ),
        help="Comma-separated sizes accepted by the selected image model.",
    )
    parser.add_argument("--offline", action="store_true", help="Validate configuration and sizes without network calls.")
    parser.add_argument("--require-verified", action="store_true", help="Treat inconclusive endpoint probes as failures.")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args(argv)

    api_key = args.api_key or gateway_api_key("IMAGE_API_KEY", "NEWAPI_API_KEY", "OPENAI_API_KEY", skill_dir=SKILL_DIR)
    operations = sorted(set(args.operation or ["generate"]))
    supported_sizes = csv_values(args.supported_sizes)
    result: dict[str, Any] = {
        "base_url": args.base_url,
        "api_key": "configured" if api_key else "missing",
        "model": args.model,
        "operations": operations,
        "requested_sizes": args.size,
        "supported_sizes": supported_sizes,
        "offline": args.offline,
        "model_check": "not_run",
        "endpoint_checks": [],
        "warnings": [],
        "errors": [],
    }

    if not args.base_url:
        result["errors"].append("AI_GATEWAY_BASE_URL is missing.")
    if not api_key:
        result["errors"].append("AI_GATEWAY_API_KEY is missing.")
    if not args.model:
        result["errors"].append("AI_IMAGE_MODEL is missing.")
    invalid_sizes = sorted(set(args.size) - set(supported_sizes))
    if invalid_sizes:
        result["errors"].append(
            "Unsupported requested size(s): " + ", ".join(invalid_sizes)
            + ". Set AI_IMAGE_SUPPORTED_SIZES only when the selected model documents those sizes."
        )

    if not result["errors"] and not args.offline:
        try:
            status, payload = request_json(args.base_url, "/v1/models", api_key, "GET", args.timeout)
            if status in {401, 403}:
                result["errors"].append(f"Gateway authentication failed while listing models (HTTP {status}).")
            elif 200 <= status < 300:
                ids = model_ids(payload)
                if ids and args.model not in ids:
                    result["errors"].append(f"Configured image model is not listed by the gateway: {args.model}")
                    result["model_check"] = "missing"
                elif ids:
                    result["model_check"] = "verified"
                else:
                    result["model_check"] = "inconclusive"
                    result["warnings"].append("The models response did not expose model IDs.")
            else:
                result["model_check"] = "inconclusive"
                result["warnings"].append(f"Could not verify model visibility (HTTP {status}).")

            for operation in operations:
                path = operation_path(operation, args.endpoint, args.model)
                status, _ = request_json(args.base_url, path, api_key, "OPTIONS", args.timeout)
                if 200 <= status < 300:
                    state = "verified"
                elif status == 405:
                    state = "route_exists_options_not_allowed"
                elif status in {401, 403}:
                    state = "authentication_failed"
                    result["errors"].append(f"Authentication failed for {path} (HTTP {status}).")
                else:
                    state = "inconclusive"
                    result["warnings"].append(f"Endpoint probe for {path} was inconclusive (HTTP {status}).")
                result["endpoint_checks"].append({"operation": operation, "path": path, "status": status, "state": state})
        except urllib.error.URLError as exc:
            result["errors"].append(f"Gateway is unreachable: {exc.reason}")

    if args.require_verified:
        for check in result["endpoint_checks"]:
            if check["state"] not in {"verified", "route_exists_options_not_allowed"}:
                result["errors"].append(f"Endpoint was not verified: {check['path']}")
        if result["model_check"] not in {"verified", "not_run"}:
            result["errors"].append("Model visibility was not verified.")

    result["ok"] = not result["errors"]
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
