#!/usr/bin/env python3
"""Append product creative scraper rows to the configured Feishu Base."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import uuid
from pathlib import Path

from export_lark_tables import (
    ASSET_FIELDS,
    PRODUCT_FIELDS,
    build_assets,
    build_products,
    expand_assets_from_scrape,
    load_json,
)


DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "references" / "lark_base_config.json"


def load_config(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Lark Base config not found: {path}")
    config = json.loads(path.read_text(encoding="utf-8"))
    missing = []
    if not config.get("base_token"):
        missing.append("base_token")
    for table_key in ("product_table", "asset_table"):
        if not config.get(table_key, {}).get("table_id"):
            missing.append(f"{table_key}.table_id")
    if missing:
        raise ValueError(
            f"Lark Base config is not initialized ({', '.join(missing)} missing). "
            "Run scripts/init_lark_base.py --create first, or pass --config with a populated config."
        )
    return config


def run_lark(args: list[str], dry_run: bool) -> None:
    printable = " ".join(args)
    if dry_run:
        print(printable)
        return
    result = subprocess.run(args, text=True, capture_output=True)
    if result.returncode != 0:
        if result.stdout:
            print(result.stdout, file=sys.stderr)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        raise RuntimeError(f"lark-cli failed: {printable}")


def batch_payload(fields: list[str], rows: list[dict]) -> dict:
    return {
        "fields": fields,
        "rows": [[row.get(field) if row.get(field) != "" else None for field in fields] for row in rows],
    }


def batch_create(base_token: str, table_id: str, fields: list[str], rows: list[dict], as_identity: str, dry_run: bool) -> int:
    count = 0
    for start in range(0, len(rows), 200):
        chunk = rows[start:start + 200]
        if not chunk:
            continue
        payload = batch_payload(fields, chunk)
        payload_path = Path.cwd() / f".lark_batch_{uuid.uuid4().hex}.json"
        payload_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        try:
            run_lark(
                [
                    "lark-cli",
                    "base",
                    "+record-batch-create",
                    "--as",
                    as_identity,
                    "--base-token",
                    base_token,
                    "--table-id",
                    table_id,
                    "--json",
                    f"@./{payload_path.name}",
                ],
                dry_run,
            )
            count += len(chunk)
        finally:
            payload_path.unlink(missing_ok=True)
        if not dry_run:
            time.sleep(0.6)
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description="Append scraper outputs to the configured Feishu Base.")
    parser.add_argument("--scrape-json", required=True)
    parser.add_argument("--analysis-json")
    parser.add_argument("--project", default="Product Creative Scan")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--as", dest="as_identity", default="user", choices=["user", "bot"])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    config = load_config(Path(args.config))
    scrape_rows = load_json(Path(args.scrape_json))
    if not isinstance(scrape_rows, list):
        raise ValueError("scrape JSON must be an array")

    if args.analysis_json:
        asset_rows = load_json(Path(args.analysis_json))
    else:
        asset_rows = expand_assets_from_scrape(scrape_rows)
    if not isinstance(asset_rows, list):
        raise ValueError("analysis JSON must be an array or object with assets")

    created_at = time.strftime("%Y-%m-%d %H:%M:%S")
    products = build_products(scrape_rows, args.project, created_at)
    assets = build_assets(asset_rows)

    base_token = config["base_token"]
    product_table_id = config["product_table"]["table_id"]
    asset_table_id = config["asset_table"]["table_id"]

    product_count = batch_create(base_token, product_table_id, PRODUCT_FIELDS, products, args.as_identity, args.dry_run)
    asset_count = batch_create(base_token, asset_table_id, ASSET_FIELDS, assets, args.as_identity, args.dry_run)

    print(json.dumps({
        "base_url": config.get("base_url"),
        "product_rows_written": product_count,
        "asset_rows_written": asset_count,
        "dry_run": args.dry_run,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
