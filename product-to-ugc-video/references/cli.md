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
  --planner-only
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
  --segment-duration 8
```

Use an existing character reference:

```bash
python3 scripts/product_to_ugc.py \
  --product-image /absolute/path/product.jpg \
  --character-reference /absolute/path/creator-reference.png \
  --description-file /absolute/path/product.txt \
  --product-name "Running Shirt"
```

## Important Flags

- `--heuristic-plan`: local fallback planner
- `--planner-only`: stop after planning outputs
- `--skip-character-generation`: skip generating the character reference image
- `--skip-frame-generation`: save prompts without generating continuous frames
- `--skip-video-generation`: save prompts and images without calling the video model
- `--skip-merge`: do not attempt final clip concatenation
- `--dry-run`: save manifests and commands without running generation

## Video Model Compatibility

The orchestrator calls `scripts/generate_video.py` for each segment. That script applies common compatibility fields for model names containing `veo` or `seedance`; confirm the exact request contract with your provider.

For both Veo and Seedance, `--duration N` is sent as:

- top-level `duration: N`
- top-level `seconds: "N"`
- `metadata.duration: N`

For Veo, it also sends:

- `metadata.durationSeconds: N`
- `metadata.aspectRatio` inferred from `--width` and `--height`

For both Veo and Seedance, `--width 720 --height 1280` is mirrored into:

- `metadata.ratio: "9:16"`
- `metadata.resolution: "720p"`

Use `scripts/generate_video.py --dry-run ...` to inspect the exact JSON payload before spending generation quota.

## Provider setup

Configure the shared gateway once before a real run:

```bash
python3 scripts/configure_ai_gateway.py
```

This configures `AI_GATEWAY_BASE_URL`, `AI_GATEWAY_API_KEY`, `AI_TEXT_MODEL`, `AI_IMAGE_MODEL`, and `AI_VIDEO_MODEL` in `~/.config/ai-gateway/config.env`. Existing `UGC_*` variables remain fallback aliases. `--heuristic-plan` avoids the planner API.

## Dependencies

This script depends on:

- `scripts/image_tool.py`
- `scripts/generate_video.py`

If `ffmpeg` is available on PATH, the script can also attempt a final merge step.
