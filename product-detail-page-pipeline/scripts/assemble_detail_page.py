#!/usr/bin/env python3
"""Assemble independently generated screens without drawing or changing text."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import pathlib
from typing import Any

from PIL import Image


SUPPORTED_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")


def read_json(path: pathlib.Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"Expected JSON object: {path}")
    return data


def write_json(path: pathlib.Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def screen_label(screen: dict[str, Any], index: int) -> str:
    raw = screen.get("screen_id", index + 1)
    try:
        return f"{int(raw):02d}"
    except (TypeError, ValueError):
        return str(raw).replace("/", "_").replace(" ", "_")


def ordered_screens(pack: dict[str, Any]) -> list[tuple[int, dict[str, Any]]]:
    screens = pack.get("screens")
    if not isinstance(screens, list) or not screens:
        raise SystemExit("prompt_pack.json must contain a non-empty screens array.")
    valid = [(index, screen) for index, screen in enumerate(screens) if isinstance(screen, dict)]

    def order(item: tuple[int, dict[str, Any]]) -> tuple[float, int]:
        index, screen = item
        plan = screen.get("assembly_plan")
        value = plan.get("order") if isinstance(plan, dict) else None
        return (float(value) if isinstance(value, (int, float)) else float(index + 1), index)

    return sorted(valid, key=order)


def find_original(image_dir: pathlib.Path, label: str) -> pathlib.Path:
    matches = [image_dir / f"screen_{label}{extension}" for extension in SUPPORTED_EXTENSIONS]
    existing = [path for path in matches if path.is_file()]
    if not existing:
        raise SystemExit(f"Missing original screen_{label} in {image_dir}")
    if len(existing) > 1:
        names = ", ".join(path.name for path in existing)
        raise SystemExit(f"Ambiguous originals for screen_{label}: {names}")
    return existing[0].resolve()


def load_rgb(path: pathlib.Path) -> Image.Image:
    with Image.open(path) as image:
        return image.convert("RGB")


def ratio_value(value: str) -> float | None:
    try:
        left, right = value.split(":", 1)
        width, height = float(left), float(right)
        return width / height if width > 0 and height > 0 else None
    except (TypeError, ValueError):
        return None


def crop_for_assembly(image: Image.Image, screen: dict[str, Any]) -> tuple[Image.Image, dict[str, Any]]:
    plan = screen.get("assembly_plan")
    if not isinstance(plan, dict) or not plan.get("crop_after_generation"):
        return image, {"operation": "none"}
    params = screen.get("backend_params")
    target_text = str(params.get("aspect_ratio") or "") if isinstance(params, dict) else ""
    target = ratio_value(target_text)
    current = image.width / image.height
    if target is None or abs(target - current) / target <= 0.01:
        return image, {"operation": "none", "target_aspect_ratio": target_text}
    if target > current:
        target_height = max(1, round(image.width / target))
        top = max(0, (image.height - target_height) // 2)
        box = (0, top, image.width, top + target_height)
    else:
        target_width = max(1, round(image.height * target))
        left = max(0, (image.width - target_width) // 2)
        box = (left, 0, left + target_width, image.height)
    cropped = image.crop(box)
    return cropped, {
        "operation": "center_crop_derivative",
        "target_aspect_ratio": target_text,
        "crop_box": list(box),
        "output_width": cropped.width,
        "output_height": cropped.height,
    }


def normalize_width(images: list[Image.Image], allow_resize: bool) -> tuple[list[Image.Image], int, bool]:
    widths = {image.width for image in images}
    if len(widths) == 1:
        return images, images[0].width, False
    if not allow_resize:
        raise SystemExit(
            "Screen widths differ. Refusing to resample. Regenerate at one width or pass --allow-resize explicitly."
        )
    target_width = images[0].width
    resized = []
    for image in images:
        if image.width == target_width:
            resized.append(image)
            continue
        target_height = round(image.height * target_width / image.width)
        resized.append(image.resize((target_width, target_height), Image.Resampling.LANCZOS))
    return resized, target_width, True


def make_long_page(images: list[Image.Image], width: int, output_path: pathlib.Path) -> None:
    page = Image.new("RGB", (width, sum(image.height for image in images)), "white")
    y = 0
    for image in images:
        page.paste(image, (0, y))
        y += image.height
    page.save(output_path, format="PNG")


def make_contact_sheet(images: list[Image.Image], output_path: pathlib.Path, columns: int) -> None:
    columns = max(1, min(columns, len(images)))
    cell_width = min(360, max(image.width for image in images))
    thumbs: list[Image.Image] = []
    for image in images:
        if image.width <= cell_width:
            thumbs.append(image.copy())
        else:
            height = round(image.height * cell_width / image.width)
            thumbs.append(image.resize((cell_width, height), Image.Resampling.LANCZOS))
    cell_height = max(image.height for image in thumbs)
    rows = math.ceil(len(thumbs) / columns)
    sheet = Image.new("RGB", (columns * cell_width, rows * cell_height), "white")
    for index, image in enumerate(thumbs):
        x = (index % columns) * cell_width + (cell_width - image.width) // 2
        y = (index // columns) * cell_height + (cell_height - image.height) // 2
        sheet.paste(image, (x, y))
    sheet.save(output_path, format="PNG")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Stitch original model-rendered screens locally without adding or changing text."
    )
    parser.add_argument("--prompt-pack", required=True, type=pathlib.Path)
    parser.add_argument("--image-dir", required=True, type=pathlib.Path)
    parser.add_argument("--output-dir", required=True, type=pathlib.Path)
    parser.add_argument("--contact-columns", type=int, default=3)
    parser.add_argument(
        "--allow-resize",
        action="store_true",
        help="Opt in to proportional resizing when original screen widths differ.",
    )
    args = parser.parse_args(argv)

    pack = read_json(args.prompt_pack)
    expected = ordered_screens(pack)
    originals: list[pathlib.Path] = []
    original_records: list[dict[str, Any]] = []
    for index, screen in expected:
        label = screen_label(screen, index)
        path = find_original(args.image_dir, label)
        with Image.open(path) as image:
            width, height = image.size
            image_format = image.format
        originals.append(path)
        original_records.append(
            {
                "screen_id": screen.get("screen_id", index + 1),
                "assembly_order": len(original_records) + 1,
                "path": str(path),
                "sha256": sha256(path),
                "width": width,
                "height": height,
                "format": image_format,
                "artifact_role": "delivered_original_screen",
            }
        )

    images: list[Image.Image] = []
    for record, path, (_, screen) in zip(original_records, originals, expected):
        prepared, transform = crop_for_assembly(load_rgb(path), screen)
        record["assembly_transform"] = transform
        images.append(prepared)
    assembly_images, width, resized = normalize_width(images, args.allow_resize)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    contact_path = args.output_dir / "contact_sheet.png"
    long_path = args.output_dir / "detail_page_long.png"
    make_contact_sheet(assembly_images, contact_path, args.contact_columns)
    make_long_page(assembly_images, width, long_path)

    for record, path in zip(original_records, originals):
        if record["sha256"] != sha256(path):
            raise SystemExit(f"Original changed during assembly: {path}")

    with Image.open(contact_path) as contact, Image.open(long_path) as long_page:
        derivatives = [
            {
                "path": str(contact_path.resolve()),
                "artifact_role": "contact_sheet",
                "sha256": sha256(contact_path),
                "width": contact.width,
                "height": contact.height,
            },
            {
                "path": str(long_path.resolve()),
                "artifact_role": "stitched_long_page",
                "sha256": sha256(long_path),
                "width": long_page.width,
                "height": long_page.height,
            },
        ]

    manifest = {
        "prompt_pack": str(args.prompt_pack.resolve()),
        "image_dir": str(args.image_dir.resolve()),
        "assembly_policy": "local pixel assembly only; no text drawing or text repair",
        "originals_preserved": True,
        "resized_for_derivatives": resized,
        "original_screens": original_records,
        "derivatives": derivatives,
    }
    manifest_path = args.output_dir / "assembly_manifest.json"
    write_json(manifest_path, manifest)
    print(
        json.dumps(
            {
                "original_screens": len(originals),
                "contact_sheet": str(contact_path.resolve()),
                "long_page": str(long_path.resolve()),
                "manifest": str(manifest_path.resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
