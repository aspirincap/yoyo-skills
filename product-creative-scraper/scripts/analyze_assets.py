#!/usr/bin/env python3
"""Analyze scraped product image URLs with OCR/VLM."""

from __future__ import annotations

import argparse
import base64
import csv
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

import requests


DEFAULT_MODEL = os.environ.get("GEMINI_VLM_MODEL", "gemini-2.5-flash")
DEFAULT_BASE_URL = os.environ.get("GEMINI_BASE_URL", "")
GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
ANALYSIS_FIELDS = [
    "image_type",
    "primary_selling_point",
    "secondary_selling_point",
    "style",
    "layout_type",
    "scene_type",
    "benefit_expression_mode",
    "visual_subjects",
    "design_elements",
    "text_on_image_raw",
    "cn_copy_summary",
    "confidence",
]


PROMPT = """You are analyzing ecommerce product creative assets.

Return one strict JSON object only. Do OCR and visual classification for this image.

Schema:
{
  "image_type": "main_image | feature_image | comparison_image | lifestyle_image | app_screenshot | app_icon | detail_image | unknown",
  "primary_selling_point": "short snake_case label",
  "secondary_selling_point": "short snake_case label or empty string",
  "style": "short snake_case visual style",
  "layout_type": "product_centered | product_with_callouts | split_screen | before_after | comparison_table | grid_features | step_by_step | hero_scene | closeup_detail | text_heavy_panel | badge_stack | testimonial_layout | bundle_flatlay | problem_solution | app_store_screenshot | unknown",
  "scene_type": "short snake_case scene label",
  "benefit_expression_mode": "feature | benefit | proof | pain_point | comparison | social_proof | instruction | unknown",
  "visual_subjects": ["short snake_case labels"],
  "design_elements": ["short snake_case labels"],
  "text_on_image_raw": "OCR text exactly as visible, or empty string",
  "cn_copy_summary": "Chinese one-sentence summary of the image message",
  "confidence": 0.0
}

Use concise snake_case labels for taxonomy-like fields. Do not include markdown.
"""


def read_scrape_rows(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        raise ValueError("scrape JSON must be an object or array")
    return [row for row in data if isinstance(row, dict)]


def expand_asset_rows(product_rows: list[dict], max_images_per_product: int) -> list[dict]:
    assets = []
    for product in product_rows:
        images = product.get("images") or []
        if isinstance(images, str):
            try:
                images = json.loads(images)
            except json.JSONDecodeError:
                images = [images]
        for idx, image_url in enumerate(images[:max_images_per_product], start=1):
            if not image_url:
                continue
            assets.append(
                {
                    "source_url": product.get("source_url") or product.get("url"),
                    "source_type": product.get("source_type"),
                    "name": product.get("name"),
                    "price": product.get("price"),
                    "image_url": image_url,
                    "image_order": idx,
                }
            )
    return assets


def mime_from_url(url: str, content_type: str | None) -> str:
    if content_type and content_type.split(";")[0].strip().startswith("image/"):
        return content_type.split(";")[0].strip()
    path = urlparse(url).path.lower()
    if path.endswith(".png"):
        return "image/png"
    if path.endswith(".webp"):
        return "image/webp"
    if path.endswith(".gif"):
        return "image/gif"
    return "image/jpeg"


def suffix_for_mime(url: str, content_type: str | None) -> str:
    path = urlparse(url).path.lower()
    for suffix in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        if path.endswith(suffix):
            return suffix
    mime_type = (content_type or "").split(";")[0].strip().lower()
    if mime_type == "image/png":
        return ".png"
    if mime_type == "image/webp":
        return ".webp"
    if mime_type == "image/gif":
        return ".gif"
    return ".jpg"


def cached_image_path(cache_dir: Path, image_url: str, content_type: str | None = None) -> Path:
    import hashlib

    suffix = suffix_for_mime(image_url, content_type)
    digest = hashlib.sha1(image_url.encode("utf-8")).hexdigest()[:16]
    return cache_dir / f"image_{digest}{suffix}"


def fetch_image(url: str, timeout: int, cache_dir: Path | None = None) -> tuple[str, str, str | None]:
    response = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0 product-creative-scraper/1.0"},
        timeout=timeout,
    )
    response.raise_for_status()
    mime_type = mime_from_url(url, response.headers.get("content-type"))
    local_path = None
    if cache_dir:
        cache_dir.mkdir(parents=True, exist_ok=True)
        image_path = cached_image_path(cache_dir, url, response.headers.get("content-type"))
        image_path.write_bytes(response.content)
        local_path = str(image_path)
    return mime_type, base64.b64encode(response.content).decode("ascii"), local_path


def extract_json_object(text: str) -> dict:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.S)
        if not match:
            raise
        return json.loads(match.group(0))


def call_google_gemini(image_url: str, model: str, api_key: str, timeout: int, cache_dir: Path | None = None) -> tuple[dict, str | None]:
    mime_type, image_b64, local_path = fetch_image(image_url, timeout, cache_dir)
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": PROMPT},
                    {"inlineData": {"mimeType": mime_type, "data": image_b64}},
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
        },
    }
    url = GEMINI_ENDPOINT.format(model=model)
    response = requests.post(f"{url}?key={api_key}", json=payload, timeout=timeout)
    response.raise_for_status()
    data = response.json()
    parts = data["candidates"][0]["content"]["parts"]
    text = "".join(part.get("text", "") for part in parts)
    return extract_json_object(text), local_path


def chat_completions_url(base_url: str) -> str:
    cleaned = base_url.rstrip("/")
    if cleaned.endswith("/chat/completions"):
        return cleaned
    if cleaned.endswith("/v1"):
        return f"{cleaned}/chat/completions"
    return f"{cleaned}/v1/chat/completions"


def call_openai_compatible_gemini(image_url: str, model: str, api_key: str, base_url: str, timeout: int, cache_dir: Path | None = None) -> tuple[dict, str | None]:
    mime_type, image_b64, local_path = fetch_image(image_url, timeout, cache_dir)
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{image_b64}"},
                    },
                ],
            }
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }
    response = requests.post(
        chat_completions_url(base_url),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    text = data["choices"][0]["message"]["content"]
    return extract_json_object(text), local_path


def call_vlm(image_url: str, model: str, api_key: str, base_url: str, timeout: int, cache_dir: Path | None = None) -> tuple[dict, str | None]:
    if base_url:
        return call_openai_compatible_gemini(image_url, model, api_key, base_url, timeout, cache_dir)
    return call_google_gemini(image_url, model, api_key, timeout, cache_dir)


def mock_analysis(asset: dict) -> dict:
    source_type = asset.get("source_type") or "unknown"
    if source_type in {"appstore", "googleplay"}:
        return {
            "image_type": "app_screenshot",
            "primary_selling_point": "app_interface",
            "secondary_selling_point": "",
            "style": "mobile_ui",
            "layout_type": "app_store_screenshot",
            "scene_type": "interface",
            "benefit_expression_mode": "feature",
            "visual_subjects": ["mobile_screen"],
            "design_elements": ["ui_text"],
            "text_on_image_raw": "",
            "cn_copy_summary": "展示移动应用界面与核心功能。",
            "confidence": 0.5,
        }
    return {
        "image_type": "product_image",
        "primary_selling_point": "product_presentation",
        "secondary_selling_point": "",
        "style": "unknown",
        "layout_type": "unknown",
        "scene_type": "unknown",
        "benefit_expression_mode": "unknown",
        "visual_subjects": ["product"],
        "design_elements": [],
        "text_on_image_raw": "",
        "cn_copy_summary": "展示商品外观和基础卖点。",
        "confidence": 0.5,
    }


def normalize_analysis(raw: dict) -> dict:
    normalized = {}
    for field in ANALYSIS_FIELDS:
        value = raw.get(field)
        if field in {"visual_subjects", "design_elements"}:
            if isinstance(value, str):
                value = [item.strip() for item in value.split(",") if item.strip()]
            elif not isinstance(value, list):
                value = []
        elif field == "confidence":
            try:
                value = float(value)
            except (TypeError, ValueError):
                value = None
        elif value is None:
            value = "" if field != "confidence" else None
        normalized[field] = value
    return normalized


def analyze_assets(assets: list[dict], args: argparse.Namespace) -> list[dict]:
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not args.mock and not api_key:
        raise RuntimeError("GEMINI_API_KEY is required unless --mock is used")

    rows = []
    for asset in assets:
        row = dict(asset)
        try:
            image_cache_path = None
            if args.mock:
                raw = mock_analysis(asset)
                if args.image_cache_dir:
                    _, _, image_cache_path = fetch_image(asset["image_url"], args.timeout, Path(args.image_cache_dir))
            else:
                raw, image_cache_path = call_vlm(
                    asset["image_url"], args.model, api_key, args.base_url, args.timeout, Path(args.image_cache_dir) if args.image_cache_dir else None
                )
            row.update(normalize_analysis(raw))
            row["image_cache_path"] = image_cache_path
            row["analysis_status"] = "ok"
            row["analysis_error"] = None
        except Exception as exc:
            for field in ANALYSIS_FIELDS:
                row[field] = [] if field in {"visual_subjects", "design_elements"} else None
            row["image_cache_path"] = None
            row["analysis_status"] = "error"
            row["analysis_error"] = str(exc)
        rows.append(row)
    return rows


def build_summary(rows: list[dict]) -> dict:
    ok_rows = [row for row in rows if row.get("analysis_status") == "ok"]
    return {
        "total_images": len(rows),
        "analyzed_images": len(ok_rows),
        "failed_images": len(rows) - len(ok_rows),
        "top_selling_points": Counter(row.get("primary_selling_point") for row in ok_rows if row.get("primary_selling_point")).most_common(10),
        "top_styles": Counter(row.get("style") for row in ok_rows if row.get("style")).most_common(10),
        "top_layouts": Counter(row.get("layout_type") for row in ok_rows if row.get("layout_type")).most_common(10),
    }


def write_csv(rows: list[dict]) -> None:
    fieldnames = [
        "source_url",
        "source_type",
        "name",
        "price",
        "image_url",
        "image_order",
        "image_cache_path",
        *ANALYSIS_FIELDS,
        "analysis_status",
        "analysis_error",
    ]
    writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        out = dict(row)
        for field in ("visual_subjects", "design_elements"):
            out[field] = json.dumps(out.get(field) or [], ensure_ascii=False)
        writer.writerow({field: out.get(field) for field in fieldnames})


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze scraped product images with OCR/VLM.")
    parser.add_argument("--scrape-json", required=True, help="JSON output from run_product_scrape.py")
    parser.add_argument("--max-images-per-product", type=int, default=3)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="OpenAI-compatible Gemini base URL")
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--format", choices=["json", "csv"], default="json")
    parser.add_argument("--include-summary", action="store_true")
    parser.add_argument("--image-cache-dir", help="Optional directory to store downloaded images for later attachment upload")
    parser.add_argument("--mock", action="store_true", help="Skip model calls and emit deterministic placeholder analysis")
    args = parser.parse_args()

    product_rows = read_scrape_rows(Path(args.scrape_json))
    assets = expand_asset_rows(product_rows, args.max_images_per_product)
    rows = analyze_assets(assets, args)

    if args.format == "csv":
        write_csv(rows)
    elif args.include_summary:
        print(json.dumps({"assets": rows, "summary": build_summary(rows)}, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
