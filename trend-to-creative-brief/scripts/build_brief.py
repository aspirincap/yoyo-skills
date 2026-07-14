#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import pathlib
import re
from typing import Any

SOURCE_WEIGHT = {"native": 5, "official": 4, "industry": 3, "media": 2, "community": 1, "unknown": 0}

def read_json(path: pathlib.Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))

def tokens(value: Any) -> set[str]:
    if isinstance(value, list):
        value = " ".join(str(item) for item in value)
    text = str(value or "").lower()
    return {item for item in re.findall(r"[a-z0-9\u4e00-\u9fff]+", text) if len(item) > 1}

def parse_date(value: str | None) -> dt.date | None:
    if not value:
        return None
    try:
        return dt.date.fromisoformat(value[:10])
    except ValueError:
        return None

def evidence_score(trend: dict[str, Any]) -> float:
    sources = trend.get("sources") or []
    weights = sorted((SOURCE_WEIGHT.get(str(s.get("source_type", "unknown")).lower(), 0) for s in sources if isinstance(s, dict)), reverse=True)
    if not weights:
        return 0.0
    return min(100.0, weights[0] * 16 + sum(weights[1:3]) * 5)

def freshness(trend: dict[str, Any], as_of: dt.date) -> tuple[float, str, str | None]:
    observed = parse_date(str(trend.get("observed_at") or ""))
    if not observed:
        return 0.0, "unknown", None
    lifecycle = max(1, int(trend.get("lifecycle_days") or 21))
    age = max(0, (as_of - observed).days)
    expires = observed + dt.timedelta(days=lifecycle)
    score = max(0.0, 100.0 * (1 - age / (lifecycle * 1.5)))
    status = "fresh" if age <= lifecycle else "aging" if age <= lifecycle * 1.5 else "stale"
    return round(score, 1), status, expires.isoformat()

def fit_score(brand: dict[str, Any], trend: dict[str, Any]) -> float:
    brand_tokens = tokens([brand.get("product"), brand.get("audience"), brand.get("positioning"), brand.get("tone"), brand.get("markets")])
    trend_tokens = tokens([trend.get("title"), trend.get("mechanic"), trend.get("tags"), trend.get("audience")])
    overlap = len(brand_tokens & trend_tokens)
    keyword_fit = min(70.0, overlap * 14.0)
    platforms = {str(x).lower() for x in brand.get("platforms", [])}
    platform_fit = 30.0 if str(trend.get("platform", "")).lower() in platforms else 10.0 if not platforms else 0.0
    return min(100.0, keyword_fit + platform_fit)

def decision(total: float, status: str, risks: list[Any]) -> str:
    if status == "stale" or len(risks) >= 3:
        return "skip"
    if total >= 72:
        return "pursue"
    if total >= 52:
        return "adapt"
    if total >= 32:
        return "watch"
    return "skip"

def build_item(brand: dict[str, Any], trend: dict[str, Any], as_of: dt.date) -> dict[str, Any]:
    e = evidence_score(trend)
    f, status, expires = freshness(trend, as_of)
    fit = fit_score(brand, trend)
    risks = trend.get("risks") if isinstance(trend.get("risks"), list) else []
    risk_penalty = min(30.0, len(risks) * 10.0)
    total = round(e * 0.4 + f * 0.25 + fit * 0.35 - risk_penalty, 1)
    choice = decision(total, status, risks)
    mechanic = str(trend.get("mechanic") or trend.get("title") or "trend mechanic")
    product = str(brand.get("product") or brand.get("brand_name") or "the product")
    sources = trend.get("sources") if isinstance(trend.get("sources"), list) else []
    return {
        "id": trend.get("id"), "title": trend.get("title"), "platform": trend.get("platform"),
        "format": trend.get("format"), "mechanic": mechanic, "observed_at": trend.get("observed_at"),
        "expires_at": expires, "freshness_status": status, "evidence_score": round(e, 1),
        "freshness_score": f, "basic_fit_score": round(fit, 1), "risk_penalty": risk_penalty,
        "total_score": total, "decision": choice, "risks": risks, "sources": sources,
        "uncertainty": trend.get("uncertainty") or "",
        "raw_provenance": trend.get("raw_provenance") if isinstance(trend.get("raw_provenance"), dict) else {},
        "creative_skeleton": {
            "hook": f"Open with the recognizable {mechanic} pattern, then reveal {product} immediately.",
            "proof": "Use one visible product fact or authorized demonstration; verify all claims.",
            "beats": ["recognizable setup", "brand-specific turn", "product proof", "payoff or CTA"],
            "distinctive_change": "Replace the source creator's exact words, footage, music, persona and artwork with original brand expression."
        }
    }

def validate(brand: Any, trends: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not isinstance(brand, dict):
        raise SystemExit("brand JSON must be an object")
    if not isinstance(trends, list) or not trends:
        raise SystemExit("trends JSON must be a non-empty array")
    for index, trend in enumerate(trends):
        if not isinstance(trend, dict):
            raise SystemExit(f"trend {index} must be an object")
        for field in ("id", "title", "platform", "mechanic", "observed_at", "sources"):
            if field not in trend:
                raise SystemExit(f"trend {index} is missing {field}")
    return brand, trends

def write_markdown(path: pathlib.Path, brand: dict[str, Any], items: list[dict[str, Any]], as_of: dt.date) -> None:
    lines = [f"# Trend-to-Creative Brief: {brand.get('brand_name') or brand.get('product') or 'Brand'}", "", f"As of: {as_of.isoformat()}", "", "## Decision Summary", "", "| Trend | Decision | Score | Freshness | Expiry |", "|---|---|---:|---|---|"]
    for item in items:
        lines.append(f"| {item['title']} | {item['decision']} | {item['total_score']} | {item['freshness_status']} | {item['expires_at'] or 'unknown'} |")
    lines.extend(["", "## Creative Skeletons", ""])
    for item in items:
        if item["decision"] not in {"pursue", "adapt"}:
            continue
        skeleton = item["creative_skeleton"]
        lines.extend([f"### {item['title']}", "", f"- Mechanic: {item['mechanic']}", f"- Hook: {skeleton['hook']}", f"- Proof: {skeleton['proof']}", f"- Beats: {' → '.join(skeleton['beats'])}", f"- Originality: {skeleton['distinctive_change']}", f"- Risks: {', '.join(str(x) for x in item['risks']) or 'none supplied'}", ""])
    lines.extend(["## Evidence and Limitations", "", "Scores are consistency aids, not performance forecasts. Verify cultural fit, rights, claims, current platform evidence and native availability before production.", ""])
    path.write_text("\n".join(lines), encoding="utf-8")

def main() -> int:
    parser = argparse.ArgumentParser(description="Build an auditable trend-to-creative scorecard and brief.")
    parser.add_argument("--brand", type=pathlib.Path, required=True)
    parser.add_argument("--trends", type=pathlib.Path, required=True)
    parser.add_argument("--as-of", default=dt.date.today().isoformat())
    parser.add_argument("--output-dir", type=pathlib.Path, required=True)
    args = parser.parse_args()
    as_of = parse_date(args.as_of)
    if not as_of:
        raise SystemExit("--as-of must be YYYY-MM-DD")
    brand, trends = validate(read_json(args.brand), read_json(args.trends))
    items = sorted((build_item(brand, trend, as_of) for trend in trends), key=lambda x: x["total_score"], reverse=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "01_trend_evidence.json").write_text(json.dumps(trends, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output_dir / "02_trend_scorecard.json").write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(args.output_dir / "03_creative_brief.md", brand, items, as_of)
    with (args.output_dir / "04_test_matrix.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=["trend_id", "decision", "variant", "variable", "learning_question"])
        writer.writeheader()
        for item in items:
            if item["decision"] in {"pursue", "adapt"}:
                writer.writerow({"trend_id": item["id"], "decision": item["decision"], "variant": "A", "variable": "hook", "learning_question": "Does the trend-native hook improve qualified attention without reducing product clarity?"})
                writer.writerow({"trend_id": item["id"], "decision": item["decision"], "variant": "B", "variable": "proof", "learning_question": "Which authorized product proof best connects the mechanic to buyer intent?"})
    print(json.dumps({"trends": len(items), "output_dir": str(args.output_dir.resolve())}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
