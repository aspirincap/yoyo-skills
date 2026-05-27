#!/usr/bin/env python3
"""Initialize the shared Feishu Base used by Product Creative Scraper."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path


DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "references" / "lark_base_config.json"
DEFAULT_TEMPLATE_BASE_TOKEN = os.environ.get("LARK_BASE_TEMPLATE_TOKEN", "")


PRODUCT_FIELDS = [
    {"name": "商品名", "type": "text"},
    {"name": "预览图", "type": "attachment"},
    {"name": "商品ID", "type": "text"},
    {"name": "项目", "type": "text"},
    {
        "name": "来源类型",
        "type": "select",
        "multiple": False,
        "options": [
            {"name": "ecommerce", "hue": "Blue", "lightness": "Lighter"},
            {"name": "appstore", "hue": "Purple", "lightness": "Lighter"},
            {"name": "googleplay", "hue": "Green", "lightness": "Lighter"},
            {"name": "unknown", "hue": "Gray", "lightness": "Lighter"},
        ],
    },
    {"name": "商品链接", "type": "text", "style": {"type": "url"}},
    {"name": "价格", "type": "number", "style": {"type": "plain", "precision": 2, "percentage": False, "thousands_separator": False}},
    {"name": "图片数量", "type": "number", "style": {"type": "plain", "precision": 0, "percentage": False, "thousands_separator": False}},
    {
        "name": "抓取状态",
        "type": "select",
        "multiple": False,
        "options": [
            {"name": "ok", "hue": "Green", "lightness": "Light"},
            {"name": "error", "hue": "Red", "lightness": "Light"},
        ],
    },
    {"name": "抓取错误", "type": "text"},
    {"name": "创建时间", "type": "datetime"},
]


ASSET_FIELDS = [
    {"name": "商品名", "type": "text"},
    {"name": "预览图", "type": "attachment"},
    {"name": "图片ID", "type": "text"},
    {"name": "商品ID", "type": "text"},
    {"name": "商品链接", "type": "text", "style": {"type": "url"}},
    {"name": "图片序号", "type": "number", "style": {"type": "plain", "precision": 0, "percentage": False, "thousands_separator": False}},
    {"name": "图片链接", "type": "text", "style": {"type": "url"}},
    {"name": "图片类型", "type": "text"},
    {"name": "主卖点", "type": "text"},
    {"name": "次卖点", "type": "text"},
    {"name": "风格", "type": "text"},
    {"name": "布局", "type": "text"},
    {"name": "场景", "type": "text"},
    {"name": "表达方式", "type": "text"},
    {"name": "图片文字", "type": "text"},
    {"name": "中文摘要", "type": "text"},
    {"name": "置信度", "type": "number", "style": {"type": "plain", "precision": 2, "percentage": False, "thousands_separator": False}},
    {
        "name": "分析状态",
        "type": "select",
        "multiple": False,
        "options": [
            {"name": "ok", "hue": "Green", "lightness": "Light"},
            {"name": "error", "hue": "Red", "lightness": "Light"},
        ],
    },
    {"name": "分析错误", "type": "text"},
    {
        "name": "是否参考",
        "type": "select",
        "multiple": False,
        "options": [
            {"name": "待定", "hue": "Gray", "lightness": "Lighter"},
            {"name": "是", "hue": "Green", "lightness": "Light"},
            {"name": "否", "hue": "Red", "lightness": "Lighter"},
        ],
    },
    {"name": "人工备注", "type": "text"},
]


def extract_json_payload(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}
    return json.loads(text[start:end + 1])


def is_base_copying(payload: dict) -> bool:
    error = payload.get("error") if isinstance(payload, dict) else None
    return bool(error and (error.get("code") == 800004046 or "base is copying" in str(error.get("message", ""))))


def run(args: list[str], retries: int = 20, retry_delay: float = 3.0) -> dict:
    for attempt in range(retries + 1):
        result = subprocess.run(args, text=True, capture_output=True)
        payload = extract_json_payload(result.stdout) or extract_json_payload(result.stderr)
        if result.returncode == 0:
            return payload
        if is_base_copying(payload) and attempt < retries:
            time.sleep(retry_delay)
            continue
        if result.stdout:
            print(result.stdout, file=sys.stderr)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        raise RuntimeError(f"command failed: {' '.join(args)}")
    raise RuntimeError(f"command failed after retries: {' '.join(args)}")


def create_base(name: str, as_identity: str) -> dict:
    return run([
        "lark-cli", "base", "+base-create",
        "--as", as_identity,
        "--name", name,
        "--time-zone", "Asia/Shanghai",
    ])["data"]["base"]


def copy_base(template_base_token: str, name: str, as_identity: str) -> dict:
    return run([
        "lark-cli", "base", "+base-copy",
        "--as", as_identity,
        "--base-token", template_base_token,
        "--name", name,
        "--time-zone", "Asia/Shanghai",
        "--without-content",
    ])["data"]["base"]


def create_table(base_token: str, name: str, fields: list[dict], view_name: str, as_identity: str) -> dict:
    payload = run([
        "lark-cli", "base", "+table-create",
        "--as", as_identity,
        "--base-token", base_token,
        "--name", name,
        "--fields", json.dumps(fields, ensure_ascii=False),
        "--view", json.dumps([{"name": view_name, "type": "grid"}], ensure_ascii=False),
    ])["data"]
    return {
        "table_id": payload["table"]["id"],
        "view_id": payload["views"][0]["id"],
        "fields": payload["fields"],
    }


def list_tables(base_token: str, as_identity: str) -> list[dict]:
    payload = run([
        "lark-cli", "base", "+table-list",
        "--as", as_identity,
        "--base-token", base_token,
        "--offset", "0",
        "--limit", "50",
    ])["data"]
    return payload.get("tables", [])


def list_fields(base_token: str, table_id: str, as_identity: str) -> list[dict]:
    payload = run([
        "lark-cli", "base", "+field-list",
        "--as", as_identity,
        "--base-token", base_token,
        "--table-id", table_id,
    ])["data"]
    return payload.get("fields", [])


def list_views(base_token: str, table_id: str, as_identity: str) -> list[dict]:
    payload = run([
        "lark-cli", "base", "+view-list",
        "--as", as_identity,
        "--base-token", base_token,
        "--table-id", table_id,
        "--offset", "0",
        "--limit", "100",
    ])["data"]
    return payload.get("views", [])


def find_by_name(items: list[dict], name: str, id_key: str = "id") -> dict:
    for item in items:
        if item.get("name") == name:
            return item
    available = ", ".join(str(item.get("name")) for item in items)
    raise KeyError(f"{name!r} not found; available: {available}")


def resolve_copied_table(base_token: str, table_name: str, view_name: str, as_identity: str) -> dict:
    table = find_by_name(list_tables(base_token, as_identity), table_name)
    table_id = table["id"]
    fields = list_fields(base_token, table_id, as_identity)
    views = list_views(base_token, table_id, as_identity)
    view = find_by_name(views, view_name)
    return {"table_id": table_id, "view_id": view["id"], "fields": fields}


def field_id(fields: list[dict], name: str) -> str:
    for field in fields:
        if field.get("name") == name:
            return field["id"]
    raise KeyError(f"field not found: {name}")


def set_visible_fields(base_token: str, table_id: str, view_id: str, fields: list[dict], names: list[str], as_identity: str) -> None:
    ids = [field_id(fields, name) for name in names]
    run([
        "lark-cli", "base", "+view-set-visible-fields",
        "--as", as_identity,
        "--base-token", base_token,
        "--table-id", table_id,
        "--view-id", view_id,
        "--json", json.dumps({"visible_fields": ids}, ensure_ascii=False),
    ])


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize the Feishu Base config for Product Creative Scraper.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--name", default="Product Creative Scraper MVP")
    parser.add_argument("--as", dest="as_identity", default="user", choices=["user", "bot"])
    parser.add_argument("--show", action="store_true", help="Only print current config")
    parser.add_argument("--create", action="store_true", help="Create a fresh Base and overwrite config")
    parser.add_argument("--template-base-token", default=DEFAULT_TEMPLATE_BASE_TOKEN, help="Optional template Base token copied for fresh init; can also be set via LARK_BASE_TEMPLATE_TOKEN")
    parser.add_argument("--from-scratch", action="store_true", help="Create tables from scratch instead of copying the template; attachment fields may be mobile-only")
    args = parser.parse_args()

    config_path = Path(args.config)
    if args.show:
        if not config_path.exists():
            raise FileNotFoundError(f"config not found: {config_path}")
        print(config_path.read_text(encoding="utf-8"))
        return 0

    if not args.create:
        if config_path.exists():
            print(config_path.read_text(encoding="utf-8"))
            return 0
        print("No config found. Pass --create to create a fresh Feishu Base.", file=sys.stderr)
        return 2

    use_template = bool(args.template_base_token) and not args.from_scratch

    if not use_template:
        base = create_base(args.name, args.as_identity)
    else:
        base = copy_base(args.template_base_token, args.name, args.as_identity)
    base_token = base["base_token"]

    if not use_template:
        product = create_table(base_token, "商品表", PRODUCT_FIELDS, "全部商品", args.as_identity)
        asset = create_table(base_token, "图片表", ASSET_FIELDS, "全部图片", args.as_identity)
    else:
        product = resolve_copied_table(base_token, "商品表", "全部商品", args.as_identity)
        asset = resolve_copied_table(base_token, "图片表", "全部图片", args.as_identity)

    # Grid views force the primary field into the first column, so keep 预览图
    # immediately after the primary ID field.
    product_order = ["商品ID", "预览图", "商品名", "项目", "来源类型", "商品链接", "价格", "图片数量", "抓取状态", "抓取错误", "创建时间"]
    asset_order = ["图片ID", "预览图", "商品名", "商品ID", "商品链接", "图片序号", "图片链接", "图片类型", "主卖点", "次卖点", "风格", "布局", "场景", "表达方式", "图片文字", "中文摘要", "置信度", "分析状态", "分析错误", "是否参考", "人工备注"]
    set_visible_fields(base_token, product["table_id"], product["view_id"], product["fields"], product_order, args.as_identity)
    set_visible_fields(base_token, asset["table_id"], asset["view_id"], asset["fields"], asset_order, args.as_identity)

    config = {
        "configured": True,
        "base_name": base["name"],
        "base_token": base_token,
        "base_url": base.get("url"),
        "time_zone": base.get("time_zone", "Asia/Shanghai"),
        "init_mode": "template_copy_without_content" if use_template else "from_scratch",
        "template_base_token": args.template_base_token if use_template else None,
        "product_table": {
            "name": "商品表",
            "table_id": product["table_id"],
            "view_id": product["view_id"],
            "preview_field_id": field_id(product["fields"], "预览图"),
        },
        "asset_table": {
            "name": "图片表",
            "table_id": asset["table_id"],
            "view_id": asset["view_id"],
            "preview_field_id": field_id(asset["fields"], "预览图"),
        },
    }
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(config, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
