#!/usr/bin/env python3
"""Create a user-reviewable, per-screen generation plan without calling an image model."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
from typing import Any

from run_image_generation import infer_size, read_json, validate_screens


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compact_copy(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value if str(item).strip()) or "—"
    return str(value).strip() if value is not None and str(value).strip() else "—"


def page_record(screen: dict[str, Any], index: int) -> dict[str, Any]:
    text = screen.get("text_to_render") if isinstance(screen.get("text_to_render"), dict) else {}
    buyer = screen.get("buyer_logic") if isinstance(screen.get("buyer_logic"), dict) else {}
    backend = screen.get("backend_params") if isinstance(screen.get("backend_params"), dict) else {}
    assembly = screen.get("assembly_plan") if isinstance(screen.get("assembly_plan"), dict) else {}
    aspect_ratio = str(backend.get("aspect_ratio") or "")
    return {
        "screen_id": screen.get("screen_id", index + 1),
        "order": assembly.get("order", index + 1),
        "role": screen.get("role", ""),
        "buyer_question": buyer.get("buyer_question", ""),
        "visual_content": screen.get("final_prompt_en")
        or screen.get("final_prompt_localized")
        or screen.get("screen_specific_prompt")
        or "",
        "customer_copy": {
            "language": text.get("language", ""),
            "kicker": text.get("kicker", ""),
            "headline": text.get("headline", ""),
            "subheadline": text.get("subheadline", ""),
            "badges": text.get("badges", []),
        },
        "copy_layout": {
            "placement": text.get("placement", ""),
            "typography": text.get("typography", ""),
            "max_lines": text.get("max_lines", {}),
        },
        "evidence_to_show": buyer.get("visual_evidence_to_show", []),
        "claims_to_avoid": buyer.get("claim_to_avoid_overstating", []),
        "negative_prompt": screen.get("negative_prompt", ""),
        "aspect_ratio": aspect_ratio,
        "render_size": backend.get("size") or infer_size(aspect_ratio, "1024x1024"),
        "reference_images": backend.get("reference_images", []),
        "assembly_plan": assembly,
    }


def markdown(review: dict[str, Any]) -> str:
    lines = [
        "# Generation Review",
        "",
        "> Status: awaiting user confirmation. No image generation has started.",
        "",
        f"Prompt Pack SHA-256: `{review['prompt_pack_sha256']}`",
        "",
        "Review every page below. Request any changes by screen number. After all pages are correct, explicitly say `开始生图` or `Start image generation`.",
        "",
    ]
    for page in review["pages"]:
        copy = page["customer_copy"]
        lines.extend(
            [
                f"## Page {page['order']} · Screen {page['screen_id']} · {compact_copy(page['role'])}",
                "",
                f"- Buyer question: {compact_copy(page['buyer_question'])}",
                f"- Visual content: {compact_copy(page['visual_content'])}",
                f"- Kicker: {compact_copy(copy['kicker'])}",
                f"- Headline: {compact_copy(copy['headline'])}",
                f"- Subheadline: {compact_copy(copy['subheadline'])}",
                f"- Badges: {compact_copy(copy['badges'])}",
                f"- Copy language: {compact_copy(copy['language'])}",
                f"- Text placement: {compact_copy(page['copy_layout']['placement'])}",
                f"- Typography: {compact_copy(page['copy_layout']['typography'])}",
                f"- Maximum lines: {compact_copy(page['copy_layout']['max_lines'])}",
                f"- Evidence to show: {compact_copy(page['evidence_to_show'])}",
                f"- Claims to avoid: {compact_copy(page['claims_to_avoid'])}",
                f"- Negative prompt: {compact_copy(page['negative_prompt'])}",
                f"- Canvas: {compact_copy(page['aspect_ratio'])} → {compact_copy(page['render_size'])}",
                f"- References: {compact_copy(page['reference_images'])}",
                f"- Assembly plan: {compact_copy(page['assembly_plan'])}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export every planned page for user review before generation.")
    parser.add_argument("--prompt-pack", required=True, type=pathlib.Path)
    parser.add_argument("--output-dir", required=True, type=pathlib.Path)
    args = parser.parse_args(argv)

    pack = read_json(args.prompt_pack)
    raw_screens = pack.get("screens")
    if not isinstance(raw_screens, list) or not raw_screens:
        raise SystemExit("prompt_pack.json must contain a non-empty screens array.")
    screens = validate_screens(raw_screens)
    pages = [page_record(screen, index) for index, screen in enumerate(screens)]
    pages.sort(key=lambda item: (item["order"], str(item["screen_id"])))
    review = {
        "status": "awaiting_user_confirmation",
        "generation_started": False,
        "prompt_pack": str(args.prompt_pack.resolve()),
        "prompt_pack_sha256": sha256(args.prompt_pack),
        "page_count": len(pages),
        "required_confirmation": ["开始生图", "确认生图", "Start image generation", "Approve image generation"],
        "pages": pages,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "generation_review.json"
    markdown_path = args.output_dir / "generation_review.md"
    json_path.write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(markdown(review), encoding="utf-8")
    print(json.dumps({"review_json": str(json_path.resolve()), "review_markdown": str(markdown_path.resolve()), "pages": len(pages)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
