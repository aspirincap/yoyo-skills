#!/usr/bin/env python3
"""Export product and image rows for the lightweight Feishu Base schema."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path


PRODUCT_FIELDS = [
    "商品ID",
    "项目",
    "来源类型",
    "商品名",
    "商品链接",
    "价格",
    "图片数量",
    "抓取状态",
    "抓取错误",
    "创建时间",
]

ASSET_FIELDS = [
    "图片ID",
    "商品ID",
    "商品名",
    "商品链接",
    "图片序号",
    "图片链接",
    "图片类型",
    "主卖点",
    "次卖点",
    "风格",
    "布局",
    "场景",
    "表达方式",
    "图片文字",
    "中文摘要",
    "置信度",
    "分析状态",
    "分析错误",
    "是否参考",
    "人工备注",
]


def stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


def load_json(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "assets" in data:
        return data["assets"]
    return data


def as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            return [value]
    return []


def product_id_for(row: dict) -> str:
    source_url = row.get("source_url") or row.get("url") or row.get("商品链接") or ""
    return stable_id("prod", source_url)


def asset_id_for(row: dict) -> str:
    image_url = row.get("image_url") or row.get("图片链接") or ""
    return stable_id("asset", image_url)


def build_products(scrape_rows: list[dict], project: str, created_at: str) -> list[dict]:
    rows = []
    for row in scrape_rows:
        images = as_list(row.get("images"))
        rows.append(
            {
                "商品ID": product_id_for(row),
                "项目": project,
                "来源类型": row.get("source_type") or "",
                "商品名": row.get("name") or "",
                "商品链接": row.get("source_url") or row.get("url") or "",
                "价格": row.get("price") if row.get("price") is not None else "",
                "图片数量": len(images),
                "抓取状态": row.get("status") or "",
                "抓取错误": row.get("error") or "",
                "创建时间": created_at,
            }
        )
    return rows


def expand_assets_from_scrape(scrape_rows: list[dict]) -> list[dict]:
    rows = []
    for product in scrape_rows:
        for idx, image_url in enumerate(as_list(product.get("images")), start=1):
            rows.append(
                {
                    "source_url": product.get("source_url") or product.get("url") or "",
                    "source_type": product.get("source_type") or "",
                    "name": product.get("name") or "",
                    "price": product.get("price"),
                    "image_url": image_url,
                    "image_order": idx,
                    "analysis_status": "",
                    "analysis_error": "",
                }
            )
    return rows


def build_assets(asset_rows: list[dict]) -> list[dict]:
    rows = []
    for row in asset_rows:
        source_url = row.get("source_url") or ""
        image_url = row.get("image_url") or ""
        rows.append(
            {
                "图片ID": asset_id_for(row),
                "商品ID": stable_id("prod", source_url),
                "商品名": row.get("name") or "",
                "商品链接": source_url,
                "图片序号": row.get("image_order") or "",
                "图片链接": image_url,
                "图片类型": row.get("image_type") or "",
                "主卖点": row.get("primary_selling_point") or "",
                "次卖点": row.get("secondary_selling_point") or "",
                "风格": row.get("style") or "",
                "布局": row.get("layout_type") or "",
                "场景": row.get("scene_type") or "",
                "表达方式": row.get("benefit_expression_mode") or "",
                "图片文字": row.get("text_on_image_raw") or "",
                "中文摘要": row.get("cn_copy_summary") or "",
                "置信度": row.get("confidence") if row.get("confidence") is not None else "",
                "分析状态": row.get("analysis_status") or "",
                "分析错误": row.get("analysis_error") or "",
                "是否参考": "待定",
                "人工备注": "",
            }
        )
    return rows


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Feishu-ready product and asset CSV files.")
    parser.add_argument("--scrape-json", required=True, help="JSON output from run_product_scrape.py")
    parser.add_argument("--analysis-json", help="JSON output from analyze_assets.py")
    parser.add_argument("--project", default="Product Creative Scan")
    parser.add_argument("--out-dir", default=".")
    args = parser.parse_args()

    scrape_rows = load_json(Path(args.scrape_json))
    if not isinstance(scrape_rows, list):
        raise ValueError("scrape JSON must be an array")

    asset_rows = (
        load_json(Path(args.analysis_json))
        if args.analysis_json
        else expand_assets_from_scrape(scrape_rows)
    )
    if not isinstance(asset_rows, list):
        raise ValueError("analysis JSON must be an array or object with assets")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    products = build_products(scrape_rows, args.project, created_at)
    assets = build_assets(asset_rows)

    products_path = out_dir / "products.csv"
    assets_path = out_dir / "assets.csv"
    write_csv(products_path, products, PRODUCT_FIELDS)
    write_csv(assets_path, assets, ASSET_FIELDS)

    print(json.dumps({
        "products_csv": str(products_path),
        "assets_csv": str(assets_path),
        "product_rows": len(products),
        "asset_rows": len(assets),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
