#!/usr/bin/env python3
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]

def main() -> int:
    skill_text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    readme_text = (ROOT / "README.md").read_text(encoding="utf-8")
    for required in (
        "https://unifapi.com/zh/mcp", "https://mcp.unifapi.com",
        "mcp__unifapi__list_operations", "mcp__unifapi__get_operation", "mcp__unifapi__call_api",
        "/tiktok/search/videos", "/instagram/search",
    ):
        assert required in skill_text, f"SKILL.md missing dependency contract: {required}"
        assert required in readme_text, f"README.md missing dependency contract: {required}"

    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        brand = {"brand_name": "Demo", "product": "insulated office bottle", "audience": ["office workers"], "platforms": ["instagram"], "positioning": ["practical"], "tone": ["witty"]}
        trends = [
            {"id": "t1", "title": "Desk personality reveal", "platform": "instagram", "format": "reel", "mechanic": "personality reveal montage", "observed_at": "2026-07-10", "lifecycle_days": 21, "tags": ["office", "personality"], "audience": ["office workers"], "risks": [], "sources": [{"url": "https://example.com/native", "source_type": "native", "published_at": "2026-07-10", "evidence": "dated example"}]},
            {"id": "t2", "title": "Old audio meme", "platform": "tiktok", "format": "video", "mechanic": "audio reaction", "observed_at": "2026-01-01", "lifecycle_days": 7, "tags": [], "audience": [], "risks": ["music rights"], "sources": [{"url": "https://example.com/blog", "source_type": "media", "published_at": "2026-01-02", "evidence": "secondary summary"}]}
        ]
        brand_path, trend_path = root / "brand.json", root / "trends.json"
        brand_path.write_text(json.dumps(brand), encoding="utf-8")
        trend_path.write_text(json.dumps(trends), encoding="utf-8")
        out = root / "out"
        result = subprocess.run([sys.executable, str(ROOT / "scripts" / "build_brief.py"), "--brand", str(brand_path), "--trends", str(trend_path), "--as-of", "2026-07-14", "--output-dir", str(out)], text=True, capture_output=True, check=False)
        assert result.returncode == 0, result.stderr
        scorecard = json.loads((out / "02_trend_scorecard.json").read_text())
        assert scorecard[0]["id"] == "t1"
        assert scorecard[0]["decision"] in {"pursue", "adapt"}
        stale = next(item for item in scorecard if item["id"] == "t2")
        assert stale["freshness_status"] == "stale"
        assert stale["decision"] == "skip"
        assert (out / "01_trend_evidence.json").exists()
        assert (out / "03_creative_brief.md").exists()
        assert (out / "04_test_matrix.csv").exists()

        tiktok_response = {
            "structuredContent": {
                "ok": True,
                "request_id": "tk-1",
                "operation": {"method": "GET", "path": "/tiktok/search/videos"},
                "data": [
                    {"id": "123", "video_description": "#ad night run loadout", "create_time": 1783814400, "duration": 15, "share_url": "https://www.tiktok.com/@runner/video/123", "view_count": 12000, "like_count": 600, "comment_count": 20, "share_count": 40, "region": "US", "hashtags": ["nightrun"], "author": {"username": "runner"}, "music": {"title": "original sound", "is_original": True}, "play_url": "https://signed.example/transient"},
                    {"id": "non-us", "video_description": "recent but off market", "create_time": 1783814400, "share_url": "https://www.tiktok.com/@runner/video/non-us", "region": "GB", "author": {"username": "runner"}},
                    {"id": "old", "video_description": "old post", "create_time": 1767225600, "share_url": "https://www.tiktok.com/@runner/video/old", "region": "US", "author": {"username": "runner"}},
                ],
                "billing": {"credits_charged": 2, "records_charged": 2},
            }
        }
        instagram_payload = {
            "ok": True,
            "request_id": "ig-1",
            "operation": {"method": "GET", "path": "/instagram/search"},
            "data": [{"shortcode": "ABC", "taken_at": 1783728000, "caption": "Visible from a distance", "product_type": "clips", "play_count": 1119, "like_count": 20, "comment_count": 1, "user": {"username": "brand"}, "location": {"name": "New York"}, "video_url": "https://signed.example/transient"}],
            "billing": {"credits_charged": 1, "records_charged": 1},
        }
        instagram_response = {"content": [{"type": "text", "text": json.dumps(instagram_payload)}]}
        tiktok_path, instagram_path, imported_path = root / "tiktok.json", root / "instagram.json", root / "public-evidence.json"
        tiktok_path.write_text(json.dumps(tiktok_response), encoding="utf-8")
        instagram_path.write_text(json.dumps(instagram_response), encoding="utf-8")
        imported = subprocess.run([
            sys.executable, str(ROOT / "scripts" / "import_public_social.py"),
            "--input", str(tiktok_path), "--input", str(instagram_path),
            "--query", "night running gear", "--query", "reflective gear",
            "--from-date", "2026-07-01", "--to-date", "2026-07-14",
            "--market", "US", "--output", str(imported_path),
        ], text=True, capture_output=True, check=False)
        assert imported.returncode == 0, imported.stderr
        converted = json.loads(imported_path.read_text())
        assert converted["coverage"] == {"total_in_window": 2, "by_platform": {"tiktok": 1, "instagram": 1}, "market_matched": 1, "market_unverified": 1}
        tiktok = next(item for item in converted["items"] if item["platform"] == "tiktok")
        instagram = next(item for item in converted["items"] if item["platform"] == "instagram")
        assert tiktok["engagement"]["views"] == 12000
        assert tiktok["market_status"] == "matched"
        assert tiktok["commercial_signal"] == "disclosed_ad"
        assert instagram["market_status"] == "unverified"
        assert instagram["url"] == "https://www.instagram.com/p/ABC/"
        assert all(item["id"] != "tiktok-non-us" for item in converted["items"])
        serialized = imported_path.read_text()
        assert "signed.example" not in serialized
        assert converted["inputs"][0]["billing"]["credits_charged"] == 2
        assert converted["inputs"][1]["query"] == "reflective gear"
    print("smoke tests passed")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
