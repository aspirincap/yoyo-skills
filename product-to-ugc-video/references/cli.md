# CLI Usage

The character-led orchestrator is:

```bash
python3 scripts/product_to_ugc.py
```

## Common Examples

Plan only:

```bash
python3 scripts/product_to_ugc.py \
  --product-image /absolute/path/product.jpg \
  --description-file /absolute/path/product.txt \
  --product-name "Running Shirt" \
  --platform TikTok \
  --heuristic-plan --planner-only
```

Dry-run full project:

```bash
python3 scripts/product_to_ugc.py \
  --product-image /absolute/path/product.jpg \
  --description "Ultra-lightweight and breathable running shirt for outdoor training" \
  --product-name "Running Shirt" \
  --project-name running-shirt-ugc \
  --segment-count 3 \
  --segment-duration 8 \
  --heuristic-plan \
  --dry-run
```

Generate a full character-led sequence:

```bash
python3 scripts/product_to_ugc.py \
  --product-image /absolute/path/product.jpg \
  --description-file /absolute/path/product.txt \
  --product-name "Running Shirt" \
  --brand-name "Acme" \
  --platform TikTok \
  --language zh-CN \
  --segment-count 3 \
  --segment-duration 8 \
  --plan-file /absolute/path/plan.json
```

Use an existing character reference:

```bash
python3 scripts/product_to_ugc.py \
  --product-image /absolute/path/product.jpg \
  --character-reference /absolute/path/creator-reference.png \
  --description-file /absolute/path/product.txt \
  --product-name "Running Shirt" \
  --plan-file /absolute/path/plan.json
```

## Important Flags

- `--heuristic-plan`: local fallback planner
- `--planner-only`: stop after planning outputs
- `--skip-character-generation`: skip generating the character reference image
- `--skip-frame-generation`: save prompts without generating continuous frames
- `--skip-video-generation`: save prompts and images without calling the video model
- `--skip-merge`: do not attempt final clip concatenation
- `--dry-run`: save manifests and commands without running generation

## MCP configuration and video anchors

Read [aicreative-mcp.md](aicreative-mcp.md). The image/video wrappers use numeric modelConfigId values and the configured MCP server. Adjacent frames map to `frame.firstFrame` and `frame.lastFrame`; they are not mixed with general references. The UGC orchestrator defaults to Wan 2.7 (1108), which supports person references, both anchors and native audio ON. Use `--no-generate-audio` only with a compatible model. Person, frame, duration, ratio and audio compatibility are checked before any image generation. Voiceover text is retained for later assembly; the runner does not implement TTS.

A real run requires `--plan-file` from the calling agent or explicit `--heuristic-plan`. Use the same project directory, plan, source files and model IDs to resume task journals. Use a new project for intentional regeneration.

## Dependencies

This script depends on:

- `scripts/image_tool.py`
- `scripts/generate_video.py`

If `ffmpeg` is available on PATH, the script can also attempt a final merge step.
