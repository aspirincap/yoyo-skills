#!/usr/bin/env python3
"""Batch wrapper for the bundled product_scraper.py module."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import sys
from pathlib import Path
from urllib.parse import urlparse


BUILTIN_SCRAPER = Path(__file__).resolve().with_name("product_scraper.py")


def load_scraper(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"bundled scraper not found: {path}")
    spec = importlib.util.spec_from_file_location("product_scraper_source", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load bundled scraper from: {path}")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except SystemExit as exc:
        raise RuntimeError(f"bundled scraper exited while loading: {path} ({exc})") from exc
    if not hasattr(module, "scrape_product"):
        raise RuntimeError("bundled scraper does not expose scrape_product(url)")
    return module


def normalize_url(value: str) -> str:
    url = value.strip()
    if not url:
        return ""
    if url.startswith("//"):
        return "https:" + url
    if not urlparse(url).scheme:
        return "https://" + url
    return url


def read_urls(args: argparse.Namespace) -> list[str]:
    urls: list[str] = []
    urls.extend(args.urls or [])

    if args.url_file:
        path = Path(args.url_file)
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                urls.append(line)

    if args.csv_file:
        path = Path(args.csv_file)
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            if args.csv_column not in (reader.fieldnames or []):
                raise ValueError(f"CSV column not found: {args.csv_column}")
            for row in reader:
                value = row.get(args.csv_column, "")
                if value:
                    urls.append(value)

    seen = set()
    result = []
    for value in urls:
        url = normalize_url(value)
        if url and url not in seen:
            seen.add(url)
            result.append(url)
    return result


def classify_source(url: str, scraper_module) -> str:
    detector = getattr(scraper_module, "detect_url_type", None)
    if callable(detector):
        try:
            return detector(url)
        except Exception:
            return "unknown"
    return "unknown"


def scrape_one(url: str, scraper_module) -> dict:
    try:
        result = scraper_module.scrape_product(url)
        source_type = classify_source(url, scraper_module)
        if not isinstance(result, dict):
            return {
                "source_url": url,
                "source_type": source_type,
                "status": "error",
                "error": "scraper returned a non-object result",
            }
        if "error" in result:
            return {
                "source_url": url,
                "source_type": source_type,
                "name": result.get("name"),
                "price": result.get("price"),
                "images": result.get("images", []),
                "status": "error",
                "error": result.get("error"),
            }
        return {
            "source_url": url,
            "source_type": source_type,
            "name": result.get("name"),
            "price": result.get("price"),
            "images": result.get("images", []),
            "status": "ok",
            "error": None,
        }
    except Exception as exc:
        return {
            "source_url": url,
            "source_type": "unknown",
            "status": "error",
            "error": str(exc),
        }


def write_csv(rows: list[dict]) -> None:
    writer = csv.DictWriter(
        sys.stdout,
        fieldnames=["source_url", "source_type", "name", "price", "images", "status", "error"],
    )
    writer.writeheader()
    for row in rows:
        out = dict(row)
        out["images"] = json.dumps(out.get("images") or [], ensure_ascii=False)
        writer.writerow(out)


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape product/app metadata from URLs with bundled product_scraper.py.")
    parser.add_argument("urls", nargs="*", help="URLs to scrape")
    parser.add_argument("--url-file", help="Plain text file with one URL per line")
    parser.add_argument("--csv-file", help="CSV file with a URL column")
    parser.add_argument("--csv-column", default="url", help="CSV URL column name")
    parser.add_argument("--format", choices=["json", "csv"], default="json")
    args = parser.parse_args()

    urls = read_urls(args)
    if not urls:
        parser.error("provide at least one URL, --url-file, or --csv-file")

    scraper_module = load_scraper(BUILTIN_SCRAPER)
    rows = [scrape_one(url, scraper_module) for url in urls]

    if args.format == "csv":
        write_csv(rows)
    else:
        print(json.dumps(rows, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
