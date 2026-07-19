#!/usr/bin/env python3
"""Record explicit user approval, bound to the exact prompt pack under review."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import re

from run_image_generation import read_json, screen_id, validate_screens
from prepare_generation_review import page_record


ACCEPTED = {
    "开始生图",
    "确认生图",
    "确认并开始生图",
    "开始生成图片",
    "start image generation",
    "approve image generation",
    "confirm and start image generation",
}


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized(value: str) -> str:
    return " ".join(value.strip().lower().split()).rstrip(".!。！")


def scoped_confirmation_ids(value: str) -> set[str] | None:
    match = re.fullmatch(r"(?:开始|确认)(?:生|生成)([0-9]+(?:\s*(?:-|,|，|、)\s*[0-9]+)*)(?:页|张)?图", value)
    if not match:
        return None
    result: set[str] = set()
    for chunk in re.split(r"\s*[,，、]\s*", match.group(1)):
        if "-" in chunk:
            start_text, end_text = re.split(r"\s*-\s*", chunk, maxsplit=1)
            start, end = int(start_text), int(end_text)
            if start <= 0 or end < start or end - start > 100:
                return None
            result.update(str(item) for item in range(start, end + 1))
        else:
            item = int(chunk)
            if item <= 0:
                return None
            result.add(str(item))
    return result


def is_explicit_confirmation(value: str) -> bool:
    return value in {normalized(item) for item in ACCEPTED} or scoped_confirmation_ids(value) is not None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a generation approval after explicit user confirmation.")
    parser.add_argument("--prompt-pack", required=True, type=pathlib.Path)
    parser.add_argument("--review", required=True, type=pathlib.Path)
    parser.add_argument("--output", required=True, type=pathlib.Path)
    parser.add_argument("--confirmation", required=True, help="The user's explicit confirmation wording.")
    parser.add_argument("--only-screen", action="append", default=[], help="Approve only these reviewed screen IDs. Repeat as needed.")
    args = parser.parse_args(argv)

    confirmation = normalized(args.confirmation)
    if not is_explicit_confirmation(confirmation):
        raise SystemExit("Confirmation is not explicit. Ask the user to say 开始生图 or Start image generation.")
    review = read_json(args.review)
    pack = read_json(args.prompt_pack)
    raw_screens = pack.get("screens")
    if not isinstance(raw_screens, list) or not raw_screens:
        raise SystemExit("prompt_pack.json must contain a non-empty screens array.")
    screens = validate_screens(raw_screens)
    prompt_hash = sha256(args.prompt_pack)
    if review.get("prompt_pack_sha256") != prompt_hash:
        raise SystemExit("The prompt pack changed after review. Export and show a new generation review before approval.")
    if review.get("status") != "awaiting_user_confirmation" or review.get("generation_started") is not False:
        raise SystemExit("The review is not in the required awaiting-user-confirmation state.")
    pages = review.get("pages")
    if not isinstance(pages, list) or any(not isinstance(page, dict) for page in pages):
        raise SystemExit("The generation review must contain a pages array of JSON objects.")
    expected_ids = {screen_id(screen, index) for index, screen in enumerate(screens)}
    expected_pages = [page_record(screen, index) for index, screen in enumerate(screens)]
    expected_pages.sort(key=lambda item: (item["order"], str(item["screen_id"])))
    try:
        reviewed_ids = {screen_id({"screen_id": page.get("screen_id")}, index) for index, page in enumerate(pages)}
    except ValueError as exc:
        raise SystemExit(f"The generation review contains an invalid screen ID: {exc}") from exc
    if (
        len(pages) != len(reviewed_ids)
        or reviewed_ids != expected_ids
        or review.get("page_count") != len(screens)
        or pages != expected_pages
        or review.get("prompt_pack") != str(args.prompt_pack.resolve())
    ):
        raise SystemExit(
            "The generation review does not cover every prompt-pack screen exactly once. "
            "Export and show a new complete review before approval."
        )
    approved_ids = list(dict.fromkeys(str(item) for item in args.only_screen if str(item).strip()))
    try:
        approved_labels = {screen_id({"screen_id": item}, index) for index, item in enumerate(approved_ids)}
    except ValueError as exc:
        raise SystemExit(f"Approval contains an invalid screen ID: {exc}") from exc
    unknown = sorted(approved_labels - reviewed_ids)
    if unknown:
        raise SystemExit("Approval references screen IDs not present in the review: " + ", ".join(unknown))
    scoped_ids = scoped_confirmation_ids(confirmation)
    if scoped_ids is not None:
        scoped_labels = {screen_id({"screen_id": item}, index) for index, item in enumerate(scoped_ids)}
        if not approved_labels or scoped_labels != approved_labels:
            raise SystemExit("The page numbers in the confirmation must exactly match --only-screen.")
    approval_scope = "selected_pages" if approved_ids else "all_pages_in_prompt_pack"
    approval = {
        "approved": True,
        "approval_scope": approval_scope,
        "approved_screen_ids": approved_ids if approved_ids else sorted(expected_ids),
        "confirmation": args.confirmation.strip(),
        "approved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "prompt_pack": str(args.prompt_pack.resolve()),
        "prompt_pack_sha256": prompt_hash,
        "review": str(args.review.resolve()),
        "review_sha256": sha256(args.review),
        "page_count": review.get("page_count"),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(approval, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"approval": str(args.output.resolve()), "approved": True, "scope": approval_scope, "approved_screen_ids": approval["approved_screen_ids"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
