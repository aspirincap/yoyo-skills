#!/usr/bin/env python3
"""Upload remote product images into the Feishu Base preview attachment fields."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse

import requests


DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "references" / "lark_base_config.json"


def load_config(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Lark Base config not found: {path}")
    config = json.loads(path.read_text(encoding="utf-8"))
    missing = []
    if not config.get("base_token"):
        missing.append("base_token")
    for table_key in ("product_table", "asset_table"):
        table = config.get(table_key, {})
        if not table.get("table_id"):
            missing.append(f"{table_key}.table_id")
        if not table.get("preview_field_id"):
            missing.append(f"{table_key}.preview_field_id")
    if missing:
        raise ValueError(
            f"Lark Base config is not initialized ({', '.join(missing)} missing). "
            "Run scripts/init_lark_base.py --create first, or pass --config with a populated config."
        )
    return config


def load_analysis_cache(path: str | None) -> dict[str, str]:
    if not path:
        return {}
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict) and "assets" in data:
        rows = data["assets"]
    elif isinstance(data, list):
        rows = data
    else:
        rows = []
    cache = {}
    for row in rows:
        image_url = row.get("image_url")
        cache_path = row.get("image_cache_path")
        if image_url and cache_path and Path(cache_path).exists():
            cache[image_url] = cache_path
    return cache


def run_json(args: list[str]) -> dict:
    result = subprocess.run(args, text=True, capture_output=True)
    if result.returncode != 0:
        if result.stdout:
            print(result.stdout, file=sys.stderr)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        raise RuntimeError(f"command failed: {' '.join(args)}")
    return json.loads(result.stdout)


def extract_json_payload(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return {}


def run_lark(args: list[str], dry_run: bool) -> dict:
    if dry_run:
        print(" ".join(args))
        return {"dry_run": True}
    result = subprocess.run(args, text=True, capture_output=True)
    if result.returncode != 0:
        if result.stdout:
            print(result.stdout, file=sys.stderr)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        raise RuntimeError(f"command failed: {' '.join(args)}")
    return extract_json_payload(result.stdout)


def attachment_was_written(payload: dict, field_id: str) -> bool:
    ignored_fields = payload.get("data", {}).get("record", {}).get("ignored_fields", [])
    for field in ignored_fields:
        if field.get("id") == field_id or field.get("name") == "预览图":
            reason = field.get("reason", "ignored")
            print(f"preview attachment ignored by Feishu Base: {reason}", file=sys.stderr)
            return False
    return True


def extract_url(value) -> str:
    if value is None:
        return ""
    text = str(value)
    match = re.search(r"\((https?://[^)]+)\)", text)
    if match:
        return match.group(1)
    if text.startswith("http://") or text.startswith("https://"):
        return text
    return ""


def has_attachment(value) -> bool:
    if not value:
        return False
    if isinstance(value, list):
        return len(value) > 0
    return True


def list_records(base_token: str, table_id: str, fields: list[str], as_identity: str) -> list[dict]:
    rows = []
    offset = 0
    while True:
        args = [
            "lark-cli",
            "base",
            "+record-list",
            "--as",
            as_identity,
            "--base-token",
            base_token,
            "--table-id",
            table_id,
            "--offset",
            str(offset),
            "--limit",
            "200",
            "--format",
            "json",
        ]
        for field in fields:
            args.extend(["--field-id", field])
        payload = run_json(args)
        data = payload.get("data", {})
        field_names = data.get("fields", fields)
        record_ids = data.get("record_id_list", [])
        values = data.get("data", [])
        for record_id, value_row in zip(record_ids, values):
            row = {"record_id": record_id}
            row.update(dict(zip(field_names, value_row)))
            rows.append(row)
        if not data.get("has_more"):
            break
        offset += len(values)
    return rows


def suffix_for_url(url: str, content_type: str | None) -> str:
    path = urlparse(url).path.lower()
    for suffix in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        if path.endswith(suffix):
            return suffix
    if content_type:
        mime = content_type.split(";")[0].strip().lower()
        if mime == "image/png":
            return ".png"
        if mime == "image/webp":
            return ".webp"
        if mime == "image/gif":
            return ".gif"
    return ".jpg"


def download_image(url: str, output_dir: Path, timeout: int) -> Path:
    response = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0 product-creative-scraper/1.0"},
        timeout=timeout,
    )
    response.raise_for_status()
    suffix = suffix_for_url(url, response.headers.get("content-type"))
    path = output_dir / f"preview_{uuid.uuid4().hex}{suffix}"
    path.write_bytes(response.content)
    return path


def upload_attachment(
    base_token: str,
    table_id: str,
    record_id: str,
    field_id: str,
    image_url: str,
    local_image_path: str | None,
    as_identity: str,
    dry_run: bool,
    timeout: int,
    stats: dict[str, int],
) -> bool:
    downloaded = False
    copied = False
    if local_image_path:
        stats["cached_files_reused"] = stats.get("cached_files_reused", 0) + 1
        source_path = Path(local_image_path)
        local_path = Path.cwd() / source_path.name
        if source_path.resolve() != local_path.resolve():
            shutil.copy2(source_path, local_path)
            copied = True
    else:
        stats["images_downloaded"] = stats.get("images_downloaded", 0) + 1
        local_path = download_image(image_url, Path.cwd(), timeout)
        downloaded = True
    try:
        payload = run_lark(
            [
                "lark-cli",
                "base",
                "+record-upload-attachment",
                "--as",
                as_identity,
                "--base-token",
                base_token,
                "--table-id",
                table_id,
                "--record-id",
                record_id,
                "--field-id",
                field_id,
                "--file",
                f"./{local_path.name}",
                "--name",
                local_path.name,
            ],
            dry_run,
        )
        return dry_run or attachment_was_written(payload, field_id)
    finally:
        if downloaded or copied:
            local_path.unlink(missing_ok=True)


def first_asset_by_product(asset_rows: list[dict]) -> dict[str, str]:
    mapping: dict[str, tuple[int, str, str | None]] = {}
    for row in asset_rows:
        product_id = str(row.get("商品ID") or "")
        image_url = extract_url(row.get("图片链接"))
        if not product_id or not image_url:
            continue
        try:
            order = int(row.get("图片序号") or 9999)
        except (TypeError, ValueError):
            order = 9999
        if product_id not in mapping or order < mapping[product_id][0]:
            mapping[product_id] = (order, image_url, row.get("图片缓存路径"))
    return {product_id: {"image_url": image_url, "cache_path": cache_path} for product_id, (_, image_url, cache_path) in mapping.items()}


def upload_asset_previews(config: dict, args: argparse.Namespace, image_cache: dict[str, str], stats: dict[str, int]) -> int:
    asset_cfg = config["asset_table"]
    rows = list_records(
        config["base_token"],
        asset_cfg["table_id"],
        ["图片ID", "商品ID", "图片序号", "图片链接", "预览图"],
        args.as_identity,
    )
    uploaded = 0
    for row in rows:
        if has_attachment(row.get("预览图")) and not args.force:
            continue
        image_url = extract_url(row.get("图片链接"))
        if not image_url:
            continue
        if upload_attachment(
            config["base_token"],
            asset_cfg["table_id"],
            row["record_id"],
            asset_cfg["preview_field_id"],
            image_url,
            image_cache.get(image_url),
            args.as_identity,
            args.dry_run,
            args.timeout,
            stats,
        ):
            uploaded += 1
            time.sleep(args.delay)
    return uploaded


def upload_product_previews(config: dict, args: argparse.Namespace, image_cache: dict[str, str], stats: dict[str, int]) -> int:
    product_cfg = config["product_table"]
    asset_cfg = config["asset_table"]
    asset_rows = list_records(
        config["base_token"],
        asset_cfg["table_id"],
        ["商品ID", "图片序号", "图片链接"],
        args.as_identity,
    )
    first_images = first_asset_by_product(asset_rows)
    product_rows = list_records(
        config["base_token"],
        product_cfg["table_id"],
        ["商品ID", "预览图"],
        args.as_identity,
    )
    uploaded = 0
    for row in product_rows:
        if has_attachment(row.get("预览图")) and not args.force:
            continue
        image_info = first_images.get(str(row.get("商品ID") or ""))
        if not image_info:
            continue
        image_url = image_info["image_url"]
        if upload_attachment(
            config["base_token"],
            product_cfg["table_id"],
            row["record_id"],
            product_cfg["preview_field_id"],
            image_url,
            image_cache.get(image_url) or image_info.get("cache_path"),
            args.as_identity,
            args.dry_run,
            args.timeout,
            stats,
        ):
            uploaded += 1
            time.sleep(args.delay)
    return uploaded


def main() -> int:
    parser = argparse.ArgumentParser(description="Upload remote image links into Feishu Base preview attachment fields.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--as", dest="as_identity", default="user", choices=["user", "bot"])
    parser.add_argument("--target", choices=["products", "assets", "all"], default="all")
    parser.add_argument("--analysis-json", help="Optional analysis JSON with image_cache_path values to avoid re-downloading images")
    parser.add_argument("--force", action="store_true", help="Re-upload even when preview attachment already exists; Feishu may append a duplicate attachment")
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--delay", type=float, default=0.6)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    config = load_config(Path(args.config))
    image_cache = load_analysis_cache(args.analysis_json)
    stats = {"cached_files_reused": 0, "images_downloaded": 0}
    result = {"base_url": config.get("base_url"), "product_previews_uploaded": 0, "asset_previews_uploaded": 0}
    if args.target in {"assets", "all"}:
        result["asset_previews_uploaded"] = upload_asset_previews(config, args, image_cache, stats)
    if args.target in {"products", "all"}:
        result["product_previews_uploaded"] = upload_product_previews(config, args, image_cache, stats)
    result.update(stats)
    result["dry_run"] = args.dry_run
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
