#!/usr/bin/env python3
"""Plan aspect-ratio adaptation for e-commerce image generation backends."""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from typing import Iterable


@dataclass
class Ratio:
    label: str
    value: float


@dataclass
class AspectPlan:
    target_ratio: str
    target_value: float
    selected_backend_ratio: str
    selected_backend_value: float
    operation: str
    content_area_hint: str
    pad_direction: str | None
    pad_fraction_of_backend_canvas: float
    crop_after_generation: bool
    split_and_stitch: bool
    segment_count: int
    overlap_fraction: float
    prompt_instruction: str
    postprocess_steps: list[str]


def parse_ratio(text: str) -> Ratio:
    raw = text.strip()
    if not raw:
        raise ValueError("Ratio cannot be empty")

    if ":" in raw:
        left, right = raw.split(":", 1)
        w = float(left.strip())
        h = float(right.strip())
        if w <= 0 or h <= 0:
            raise ValueError(f"Invalid ratio: {text}")
        return Ratio(label=f"{w:g}:{h:g}", value=w / h)

    value = float(raw)
    if value <= 0:
        raise ValueError(f"Invalid ratio: {text}")
    return Ratio(label=f"{value:g}:1", value=value)


def parse_supported(text: str) -> list[Ratio]:
    ratios = [parse_ratio(item) for item in text.split(",") if item.strip()]
    if not ratios:
        raise ValueError("At least one supported ratio is required")
    return ratios


def nearest_ratio(target: Ratio, supported: Iterable[Ratio]) -> Ratio:
    return min(supported, key=lambda r: abs(math.log(r.value / target.value)))


def plan(target: Ratio, supported: list[Ratio], long_ratio_threshold: float = 4.0) -> AspectPlan:
    selected = nearest_ratio(target, supported)

    # value is width / height. Smaller means taller.
    is_extra_tall = target.value < 1 / long_ratio_threshold
    is_extra_wide = target.value > long_ratio_threshold
    split_and_stitch = False

    if is_extra_tall or is_extra_wide:
        if is_extra_tall:
            max_segment_value = min(r.value for r in supported)
            segment_count = max(2, math.ceil(max_segment_value / target.value))
            operation = "decompose_into_vertical_modules"
            content_area_hint = "Redesign the tall visual as independent vertical modules with a common width."
            prompt_instruction = (
                "Generate one complete product-detail module per image-model call. Keep visual DNA, lighting, "
                "background material, product rendering, and width consistent across modules. Do not create "
                "overlapping fragments of one canvas and do not request the complete long page in one image."
            )
        else:
            max_segment_value = max(r.value for r in supported)
            segment_count = max(2, math.ceil(target.value / max_segment_value))
            operation = "decompose_into_horizontal_modules"
            content_area_hint = "Redesign the wide visual as independent horizontal modules with a common height."
            prompt_instruction = (
                "Generate one complete product-detail module per image-model call. Keep visual DNA, lighting, "
                "background material, product rendering, and height consistent across modules. Do not create "
                "overlapping fragments of one canvas."
            )

        return AspectPlan(
            target_ratio=target.label,
            target_value=round(target.value, 6),
            selected_backend_ratio=selected.label,
            selected_backend_value=round(selected.value, 6),
            operation=operation,
            content_area_hint=content_area_hint,
            pad_direction=None,
            pad_fraction_of_backend_canvas=0.0,
            crop_after_generation=False,
            split_and_stitch=False,
            segment_count=segment_count,
            overlap_fraction=0.0,
            prompt_instruction=prompt_instruction,
            postprocess_steps=[
                f"Plan {segment_count} self-contained modules with distinct buyer questions.",
                "Generate every module independently using the same shared visual DNA and pixel width.",
                "Preserve every original module image.",
                "Stack modules locally in narrative order without overlap or text repair.",
            ],
        )

    if math.isclose(target.value, selected.value, rel_tol=0.01):
        return AspectPlan(
            target_ratio=target.label,
            target_value=round(target.value, 6),
            selected_backend_ratio=selected.label,
            selected_backend_value=round(selected.value, 6),
            operation="direct_generate",
            content_area_hint="Use the full canvas.",
            pad_direction=None,
            pad_fraction_of_backend_canvas=0.0,
            crop_after_generation=False,
            split_and_stitch=False,
            segment_count=1,
            overlap_fraction=0.0,
            prompt_instruction="Generate directly at the target aspect ratio.",
            postprocess_steps=[],
        )

    if target.value > selected.value:
        # Target is wider than backend canvas. Pad vertical space, then crop top/bottom.
        content_fraction = selected.value / target.value
        pad_fraction = max(0.0, 1.0 - content_fraction)
        pad_direction = "top_and_bottom_or_bottom_safe_area"
        instruction = (
            f"Keep all meaningful content inside the central {content_fraction:.0%} height of the canvas; "
            "outer padded height is safe extension area for later crop."
        )
    else:
        # Target is taller than backend canvas. Pad horizontal space, then crop sides.
        content_fraction = target.value / selected.value
        pad_fraction = max(0.0, 1.0 - content_fraction)
        pad_direction = "left_and_right_safe_area"
        instruction = (
            f"Keep all meaningful content inside the central {content_fraction:.0%} width of the canvas; "
            "outer padded width is safe extension area for later crop."
        )

    return AspectPlan(
        target_ratio=target.label,
        target_value=round(target.value, 6),
        selected_backend_ratio=selected.label,
        selected_backend_value=round(selected.value, 6),
        operation="pad_generate_crop",
        content_area_hint=instruction,
        pad_direction=pad_direction,
        pad_fraction_of_backend_canvas=round(pad_fraction, 6),
        crop_after_generation=True,
        split_and_stitch=False,
        segment_count=1,
        overlap_fraction=0.0,
        prompt_instruction=instruction,
        postprocess_steps=[
            f"Prepare or request backend canvas at {selected.label}.",
            "Keep important content inside the safe content area.",
            f"Crop generated output back to exact target ratio {target.label}.",
        ],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Plan aspect-ratio adaptation for image generation.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--target-ratio", help="Target ratio as W:H, such as 1:2.7 or 4:3.")
    source.add_argument("--width", type=float, help="Target width in pixels. Requires --height.")
    parser.add_argument("--height", type=float, help="Target height in pixels. Use with --width.")
    parser.add_argument(
        "--supported-ratios",
        default="1:1,4:5,3:4,2:3,9:16,1:4",
        help="Comma-separated backend-supported ratios.",
    )
    parser.add_argument("--long-ratio-threshold", type=float, default=4.0)
    args = parser.parse_args()

    if args.width is not None:
        if args.height is None or args.width <= 0 or args.height <= 0:
            raise SystemExit("--width requires a positive --height")
        target = Ratio(label=f"{args.width:g}:{args.height:g}", value=args.width / args.height)
    else:
        target = parse_ratio(args.target_ratio)

    supported = parse_supported(args.supported_ratios)
    result = plan(target, supported, args.long_ratio_threshold)
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
