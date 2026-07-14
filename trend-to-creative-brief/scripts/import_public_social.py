#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
from typing import Any, Iterable


def read_json(path: pathlib.Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSON in {path}: {exc}") from exc


def unwrap(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        result: list[dict[str, Any]] = []
        for item in value:
            result.extend(unwrap(item))
        return result
    if not isinstance(value, dict):
        return []
    structured = value.get("structuredContent")
    if isinstance(structured, dict):
        return unwrap(structured)
    content = value.get("content")
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str):
                try:
                    parsed = json.loads(block["text"])
                except json.JSONDecodeError:
                    continue
                return unwrap(parsed)
    if isinstance(value.get("data"), list):
        return [value]
    return []


def date_from_epoch(value: Any) -> str | None:
    try:
        return dt.datetime.fromtimestamp(int(value), tz=dt.timezone.utc).date().isoformat()
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def in_window(value: str | None, start: dt.date, end: dt.date) -> bool:
    if not value:
        return False
    try:
        day = dt.date.fromisoformat(value)
    except ValueError:
        return False
    return start <= day <= end


def operation_path(payload: dict[str, Any]) -> str:
    operation = payload.get("operation")
    if isinstance(operation, dict) and operation.get("path"):
        return str(operation["path"])
    return str(payload.get("path") or "")


def platform_for(payload: dict[str, Any]) -> str | None:
    path = operation_path(payload).lower()
    if "tiktok" in path:
        return "tiktok"
    if "instagram" in path:
        return "instagram"
    return None


def cleaned_engagement(**values: Any) -> dict[str, int | float]:
    result: dict[str, int | float] = {}
    for key, value in values.items():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            result[key] = value
    return result


def market_code(value: str) -> str:
    normalized = value.strip().upper()
    return {"UNITED STATES": "US", "USA": "US", "U.S.": "US", "U.S.A.": "US"}.get(normalized, normalized)


def normalize_tiktok(item: dict[str, Any], market: str) -> dict[str, Any] | None:
    item_id = str(item.get("id") or "").strip()
    url = str(item.get("share_url") or "").strip()
    published = date_from_epoch(item.get("create_time"))
    if not item_id or not url or not published:
        return None
    author = item.get("author") if isinstance(item.get("author"), dict) else {}
    region = str(item.get("region") or "").upper()
    target = market_code(market)
    text = str(item.get("video_description") or item.get("title") or "").strip()
    lowered = text.lower()
    return {
        "id": f"tiktok-{item_id}",
        "platform": "tiktok",
        "url": url,
        "published_at": published,
        "author": f"@{author.get('username')}" if author.get("username") else "",
        "text": text,
        "format": "image_post" if item.get("is_image_post") else "video",
        "duration_seconds": item.get("duration"),
        "hashtags": list(item.get("hashtags") or []),
        "engagement": cleaned_engagement(
            views=item.get("view_count"), likes=item.get("like_count"),
            comments=item.get("comment_count"), shares=item.get("share_count"),
        ),
        "market_status": "matched" if region and region == target else "mismatched" if region else "unverified",
        "market_evidence": {"region": region or None},
        "commercial_signal": "disclosed_ad" if "#ad" in lowered else "unknown",
        "music": {
            "title": item.get("music", {}).get("title"),
            "is_original": item.get("music", {}).get("is_original"),
        } if isinstance(item.get("music"), dict) else {},
    }


def normalize_instagram(item: dict[str, Any], market: str) -> dict[str, Any] | None:
    shortcode = str(item.get("shortcode") or item.get("id") or "").strip()
    published = date_from_epoch(item.get("taken_at"))
    if not shortcode or not published:
        return None
    user = item.get("user") if isinstance(item.get("user"), dict) else {}
    location = item.get("location") if isinstance(item.get("location"), dict) else {}
    text = str(item.get("caption") or "").strip()
    lowered = text.lower()
    return {
        "id": f"instagram-{shortcode}",
        "platform": "instagram",
        "url": f"https://www.instagram.com/p/{shortcode}/",
        "published_at": published,
        "author": f"@{user.get('username')}" if user.get("username") else "",
        "text": text,
        "format": "reel" if item.get("product_type") == "clips" else str(item.get("product_type") or "post"),
        "hashtags": re.findall(r"#([\w\u4e00-\u9fff]+)", text),
        "engagement": cleaned_engagement(
            plays=item.get("play_count"), views=item.get("view_count"),
            likes=item.get("like_count"), comments=item.get("comment_count"),
        ),
        "market_status": "unverified",
        "market_evidence": {"target_market": market, "location_name": location.get("name")},
        "commercial_signal": "paid_partnership" if item.get("is_paid_partnership") else "disclosed_ad" if "#ad" in lowered else "unknown",
    }


def normalize(payload: dict[str, Any], market: str) -> Iterable[dict[str, Any]]:
    platform = platform_for(payload)
    for item in payload.get("data") or []:
        if not isinstance(item, dict):
            continue
        normalized = normalize_tiktok(item, market) if platform == "tiktok" else normalize_instagram(item, market) if platform == "instagram" else None
        if normalized:
            yield normalized


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize public TikTok/Instagram API responses for trend analysis.")
    parser.add_argument("--input", type=pathlib.Path, action="append", required=True)
    parser.add_argument("--query", action="append", default=[])
    parser.add_argument("--from-date", required=True)
    parser.add_argument("--to-date", required=True)
    parser.add_argument("--market", required=True)
    parser.add_argument("--include-off-market", action="store_true", help="Retain explicit market mismatches instead of filtering them out.")
    parser.add_argument("--output", type=pathlib.Path, required=True)
    args = parser.parse_args()
    try:
        start, end = dt.date.fromisoformat(args.from_date), dt.date.fromisoformat(args.to_date)
    except ValueError as exc:
        raise SystemExit("--from-date and --to-date must be YYYY-MM-DD") from exc
    if start > end:
        raise SystemExit("--from-date must not be after --to-date")

    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    inputs: list[dict[str, Any]] = []
    for index, path in enumerate(args.input):
        query = args.query[index] if index < len(args.query) else ""
        payloads = unwrap(read_json(path))
        if not payloads:
            raise SystemExit(f"{path} contains no supported public social API response")
        for payload in payloads:
            billing = payload.get("billing") if isinstance(payload.get("billing"), dict) else {}
            inputs.append({
                "input": path.name,
                "query": query,
                "operation_path": operation_path(payload),
                "request_id": payload.get("request_id"),
                "returned_records": len(payload.get("data") or []),
                "billing": billing,
            })
            for item in normalize(payload, args.market):
                if item["id"] in seen or not in_window(item.get("published_at"), start, end):
                    continue
                if item["market_status"] == "mismatched" and not args.include_off_market:
                    continue
                seen.add(item["id"])
                items.append(item)

    items.sort(key=lambda item: (item["published_at"], item["platform"], item["id"]), reverse=True)
    output = {
        "generated_at": dt.datetime.now(tz=dt.timezone.utc).isoformat(),
        "window": {"from": start.isoformat(), "to": end.isoformat()},
        "target_market": args.market,
        "inputs": inputs,
        "items": items,
        "coverage": {
            "total_in_window": len(items),
            "by_platform": {platform: sum(1 for item in items if item["platform"] == platform) for platform in ("tiktok", "instagram")},
            "market_matched": sum(1 for item in items if item["market_status"] == "matched"),
            "market_unverified": sum(1 for item in items if item["market_status"] == "unverified"),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"items": len(items), "output": str(args.output.resolve())}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
