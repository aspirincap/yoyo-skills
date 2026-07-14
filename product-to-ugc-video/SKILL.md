---
name: product-to-ugc-video
description: Turn a product image plus product description into a character-led UGC video project. Use when Codex should plan a stable creator persona, generate a character reference, create continuous keyframes, call local image and video generation scripts for Veo or Seedance, and prepare adjacent-frame video segments plus merge metadata for a final short-form social video.
license: MIT
compatibility: Python 3.10+, configurable OpenAI-compatible planning/image endpoints and a compatible asynchronous video endpoint; ffmpeg is optional for merging.
---

# Product To UGC Video

## What This Skill Does

This skill turns a product image and a product description into a character-first UGC production package:

- a structured creator continuity plan
- a stable character reference image
- continuous scene keyframes for the same creator
- adjacent-frame video prompts and generated clips
- manifests, prompts, logs, and merge metadata

Use this skill when the user wants real execution, not just brainstorming.

## When To Use It

Use this skill when the user asks for any of the following:

- product-to-UGC generation
- product image to creator UGC workflow
- product image plus description to a creator-style short video
- stable-character short-form social video generation
- continuous keyframes plus adjacent-frame video generation
- a repeatable pipeline that uses local `scripts/image_tool.py` and `scripts/generate_video.py`

If the user only wants a conceptual plan, you can stop after the planning outputs. If the user wants generated assets, call `scripts/product_to_ugc.py`.

## Inputs To Collect

Collect these inputs when available:

- product image path
- product description
- product name
- brand name
- platform
- language
- target audience
- preferred tone
- optional existing character reference image
- creator gender, age, or style if the user has preferences
- scene setting if the user has preferences
- desired segment count and segment duration

If demographic fields are missing, keep them unspecified or choose a product-relevant neutral casting brief. Do not silently default to a particular gender, age, ethnicity, or body type.

## Workflow

1. Generate or load a structured character continuity plan.
2. Generate a stable character reference image unless the user already provided one.
3. Save prompts and manifests into a project folder.
4. Generate continuous keyframes through `scripts/image_tool.py`.
5. Generate Veo or Seedance video segments through `scripts/generate_video.py` using adjacent frames as first and last anchors.
6. Save an assembly manifest and merge metadata for final stitching.

## Provider Compatibility

`scripts/generate_video.py` includes common compatibility fields for gateway models whose name contains `veo` or `seedance`.

When `--duration N` is used, the script keeps the top-level `duration` field and also sends provider-compatible duration fields:

- `seconds: "N"` for task adaptors that only forward `seconds`
- `metadata.duration: N`
- `metadata.durationSeconds: N` for Veo models

When `--width` and `--height` are provided, the script mirrors inferred vertical or horizontal format hints into metadata:

- `metadata.ratio`, for example `9:16`
- `metadata.aspectRatio`, for Veo models
- `metadata.resolution`, for example `720p`

Provider behavior is not standardized. Inspect `--dry-run` output and compare it with provider documentation before a paid request. No private gateway is configured by default.

## Script Entry Point

Use:

```bash
python3 scripts/product_to_ugc.py --product-image ... --description ...
```

Read [references/cli.md](references/cli.md) for common command patterns and [references/project-layout.md](references/project-layout.md) for the output structure.

## Planner Behavior

By default the script uses a chat-completions model to produce a structured JSON plan for:

- creator identity
- character reference prompt
- continuous keyframe prompts
- adjacent-frame video prompts

Use `--heuristic-plan` when:

- the user wants a deterministic local fallback
- the planner API is unavailable
- you want a dry-run that avoids planner costs

## Output Contract

The project should contain:

- `project.json`
- `planning/plan.json`
- `planning/plan_summary.md`
- `prompts/character_reference.prompt.txt`
- `prompts/frames/*.prompt.txt`
- `prompts/segments/*.prompt.txt`
- `prompts/segments/*.voiceover.txt`
- `character_reference/*.png`
- `continuous_frames/*.png`
- `video_segments/*.mp4`
- `manifests/assembly_manifest.json`
- `manifests/merge_manifest.json`
- `logs/command_log.json`

## Reference Files

- Read [references/cli.md](references/cli.md) when you need exact CLI usage.
- Read [references/project-layout.md](references/project-layout.md) when you need to inspect or explain project outputs.
- Read [references/modes.md](references/modes.md) when deciding which creator route to use.

## Public-Release Rules

- Require explicit provider URLs and model IDs; do not assume a company gateway.
- Preserve visible product structure, label placement, color, and usage. Do not invent certifications, results, reviews, or before/after claims.
- Start with `--heuristic-plan --dry-run` to inspect prompts and manifests without spending quota.
- Treat customer images, generated faces, API responses, and project folders as private unless redistribution rights are clear.
- Preserve successful assets when retrying a failed segment; do not regenerate the entire project without a reason.
