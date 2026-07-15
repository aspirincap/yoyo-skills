#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
TikTok video downloader.

Uses yt-dlp to download public TikTok videos. Browser cookies are optional and
may be used only with explicit consent for the user's own authorized session;
they must not be used to bypass private, age, or regional access restrictions.

Usage:
    uv run download_tiktok.py --urls "https://www.tiktok.com/@user/video/123"
    uv run download_tiktok.py --urls "Check this out https://vm.tiktok.com/xxxx/"
    uv run download_tiktok.py --cookies-browser chrome --output-dir /path/to/output
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


TIKTOK_URL_RE = re.compile(
    r"https?://(?:www\.)?(?:tiktok\.com|vm\.tiktok\.com|vt\.tiktok\.com|m\.tiktok\.com)[^\s'\"<>]*",
    re.IGNORECASE,
)


def extract_tiktok_urls(texts: list[str]) -> list[str]:
    """Extract TikTok URLs from raw URLs or share text."""
    urls: list[str] = []
    for text in texts:
        text = text.strip()
        if re.match(r"^https?://", text) and "tiktok.com" in text.lower():
            urls.append(text)
        else:
            urls.extend(TIKTOK_URL_RE.findall(text))

    cleaned: list[str] = []
    seen: set[str] = set()
    for url in urls:
        url = url.rstrip(").,，。")
        if url not in seen:
            cleaned.append(url)
            seen.add(url)
    return cleaned


def extract_video_id(url: str) -> str:
    """Try to extract a stable video id; fall back to a URL slug."""
    match = re.search(r"/video/(\d+)", url)
    if match:
        return match.group(1)
    slug = re.sub(r"[^\w]", "", url)
    return slug[-16:] or "video"


def build_command(
    url: str,
    output_template: str,
    cookies_browser: str | None,
    proxy: str | None,
) -> list[str]:
    cmd = [
        "yt-dlp",
        "--output",
        output_template,
        "--no-warnings",
        "--merge-output-format",
        "mp4",
    ]
    if cookies_browser:
        cmd.extend(["--cookies-from-browser", cookies_browser])
    if proxy:
        cmd.extend(["--proxy", proxy])
    cmd.append(url)
    return cmd


def download_video(
    url: str,
    output_dir: Path,
    index: int,
    cookies_browser: str | None,
    proxy: str | None,
) -> dict:
    """Download a single TikTok video with yt-dlp."""
    video_id = extract_video_id(url)
    output_template = str(output_dir / f"tiktok-{index}-{video_id}.%(ext)s")
    cmd = build_command(url, output_template, cookies_browser, proxy)

    print(f"  [{index}] Downloading: {url}", file=sys.stderr)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if result.returncode != 0:
            error_msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
            if proxy:
                error_msg = error_msg.replace(proxy, "[REDACTED_PROXY]")
            lower = error_msg.lower()
            if "cookies" in lower or "login" in lower:
                error_msg = f"Login/cookies may be required: {error_msg[:240]}"
            elif "unavailable" in lower or "private" in lower or "not found" in lower:
                error_msg = f"Video unavailable/private/not found: {error_msg[:240]}"
            print(f"  [{index}] Failed: {error_msg}", file=sys.stderr)
            return {"url": url, "success": False, "error": error_msg}

        downloaded = list(output_dir.glob(f"tiktok-{index}-{video_id}.*"))
        video_files = [
            f for f in downloaded
            if f.suffix.lower() in (".mp4", ".webm", ".mkv", ".mov")
        ]

        if not video_files:
            print(f"  [{index}] Finished but no video file was found", file=sys.stderr)
            return {
                "url": url,
                "success": False,
                "error": "Download finished but no video file was found",
            }

        file_path = video_files[0]
        size_mb = file_path.stat().st_size / (1024 * 1024)
        print(f"  [{index}] Success: {file_path.name} ({size_mb:.1f}MB)", file=sys.stderr)
        return {
            "url": url,
            "success": True,
            "path": str(file_path),
            "size_mb": round(size_mb, 1),
        }

    except subprocess.TimeoutExpired:
        print(f"  [{index}] Timeout after 180 seconds", file=sys.stderr)
        return {"url": url, "success": False, "error": "Timeout after 180 seconds"}
    except FileNotFoundError:
        print("  yt-dlp not found. Install with: pip install yt-dlp or brew install yt-dlp", file=sys.stderr)
        return {"url": url, "success": False, "error": "yt-dlp is not installed"}


def main() -> None:
    parser = argparse.ArgumentParser(description="TikTok video downloader")
    parser.add_argument(
        "--urls", "-u", nargs="+", required=True,
        help="TikTok URLs or share text. Processes up to 5 videos.",
    )
    parser.add_argument(
        "--output-dir", "-o",
        default=str(Path.cwd() / "_temp" / "tiktok-downloads"),
        help="Output directory. Default: ./_temp/tiktok-downloads/",
    )
    parser.add_argument(
        "--cookies-browser", "-c", default=None,
        help="Optional browser for cookies: chrome, edge, firefox, safari.",
    )
    parser.add_argument(
        "--proxy", default=None,
        help="Optional proxy URL for yt-dlp, e.g. socks5://127.0.0.1:7890",
    )

    args = parser.parse_args()

    urls = extract_tiktok_urls(args.urls)
    if not urls:
        print("Error: no valid TikTok URL found in input", file=sys.stderr)
        print("Supported examples:", file=sys.stderr)
        print("  - https://www.tiktok.com/@user/video/123", file=sys.stderr)
        print("  - https://vm.tiktok.com/xxxx/", file=sys.stderr)
        print("  - share text containing a TikTok URL", file=sys.stderr)
        sys.exit(1)

    if len(urls) > 5:
        print(f"Warning: got {len(urls)} URLs; only processing the first 5", file=sys.stderr)
        urls = urls[:5]

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Preparing to download {len(urls)} video(s) to {output_dir}", file=sys.stderr)
    if args.cookies_browser:
        print(f"Using browser cookies from: {args.cookies_browser}", file=sys.stderr)
    if args.proxy:
        print("Using proxy: configured (value redacted)", file=sys.stderr)
    print("", file=sys.stderr)

    results = [
        download_video(url, output_dir, i, args.cookies_browser, args.proxy)
        for i, url in enumerate(urls, 1)
    ]

    success_count = sum(1 for result in results if result["success"])
    fail_count = len(results) - success_count

    print("", file=sys.stderr)
    print(f"Done: {success_count} succeeded, {fail_count} failed", file=sys.stderr)
    if fail_count:
        print("", file=sys.stderr)
        print("If downloads failed, try:", file=sys.stderr)
        print("  1. Confirm the TikTok link is public and accessible in your browser", file=sys.stderr)
        print("  2. Add --cookies-browser chrome/edge/firefox", file=sys.stderr)
        print("  3. Add --proxy if TikTok is blocked on this network", file=sys.stderr)
        print("  4. Manually download the video and place it in the output directory", file=sys.stderr)

    output = {
        "total": len(results),
        "success": success_count,
        "failed": fail_count,
        "output_dir": str(output_dir),
        "results": results,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
