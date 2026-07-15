---
name: script-to-storyboard-video
description: Turn an existing advertising script plus product images into storyboard sheets, stop for explicit human approval, then generate vertical ad clips through a configurable NewAPI-compatible image/video gateway. Use when the user already has an ad script or explicitly requests a storyboard-first approval workflow. Do not use for creator-persona development, character-reference generation, continuous keyframes, or character-led UGC; use product-to-ugc-video for those requests.
---

# Script To Storyboard Video

This skill turns an advertising script plus product image(s) into a staged production package:

1. **Storyboard stage:** generate one or more storyboard sheets from the script, product image, and target duration using the configured image model.
2. **Approval gate:** stop and show the storyboard(s). Do not generate video until the user explicitly confirms the storyboard is OK.
3. **Video stage:** use the approved storyboard sheet(s) as visual references and call the configured compatible video endpoint to generate 9:16 clips with audio.

It is intentionally narrower than `product-to-ugc-video`: it does not build a creator persona, character sheet, or adjacent-frame UGC plan. It is for ad storyboard production and direct compatible video execution.

## Bundled Scripts

The skill includes self-contained provider wrappers:

- `scripts/image_tool.py`: vendored OpenAI-format image generation/editing runtime used for storyboards.
- `scripts/generate_video.py`: vendored `/v1/video/generations` runtime. Provider-specific fields may require `--extra` or `--metadata`.
- `scripts/script_to_storyboard_video.py`: thin orchestration layer for this skill's two-stage workflow.
- `scripts/configure_ai_gateway.py`: securely configure the shared gateway once for all supported skills.

The vendored provider wrappers are generated from the repository's `shared/media-runtime/` source so this skill remains independently installable without maintaining divergent copies.

Read this file first. Only open script source if you need to debug parameters or patch behavior.

## Environment

Prefer the shared provider-neutral configuration:

```bash
python3 scripts/configure_ai_gateway.py
```

This writes `~/.config/ai-gateway/config.env` with restricted file permissions. Configure once, then reuse it from `product-creative-scraper`, `open-tiktok-script`, this skill, and `product-to-ugc-video`.

Primary variables:

- `AI_GATEWAY_BASE_URL`: NewAPI-compatible root URL, without `/v1/...`
- `AI_GATEWAY_API_KEY`: model API token sent as Bearer auth
- `AI_IMAGE_MODEL`: provider image model ID
- `AI_VIDEO_MODEL`: provider video model ID

Configuration precedence is shell environment, skill-local `.env`, shared global config, then defaults. Legacy `AD_STORYBOARD_*`, `IMAGE_API_*`, `VIDEO_API_*`, `OPENAI_*`, and `NEWAPI_*` variables remain supported.

Never commit a real `.env` or global configuration file.

## Inputs

Collect or infer:

- ad script text or a script file
- one or more product image paths
- target total duration
- desired output language for storyboard labels
- optional product notes, compliance constraints, aspect ratio, segment duration

Defaults:

- storyboard model: `AI_IMAGE_MODEL` or `gpt-image-1`
- storyboard sheet size: `2048x1152`
- storyboard sheet aspect: `16:9`
- video model: `AI_VIDEO_MODEL`; configure a non-fast model when final quality matters
- video output: `9:16`, `720x1280`, `720p`, audio on
- segment duration: `15s`; total durations above 15s become multiple storyboard/video segments

## Stage 1: Generate Storyboards

Use the `storyboard` subcommand. It writes a recoverable project folder with:

```text
project.json
inputs/ad_script.txt
prompts/storyboards/*.prompt.txt
storyboards/*.png
logs/*.json
```

Example:

```bash
python3 scripts/script_to_storyboard_video.py storyboard \
  --script-file /absolute/path/script.txt \
  --product-image /absolute/path/product.png \
  --duration 30 \
  --project-name body-oil-cream-ad \
  --api-key-env AI_GATEWAY_API_KEY
```

After the command finishes:

1. Show the generated storyboard image(s) inline.
2. Give the `project_dir`.
3. Ask the user to confirm or request changes.
4. Do not proceed to video generation unless the user explicitly confirms.

## Stage 2: Generate Videos

After approval, use the `video` subcommand with `--confirmed`. It reads `project.json`, creates video prompts, and generates one clip per approved storyboard segment.

Example:

```bash
python3 scripts/script_to_storyboard_video.py video \
  --project-dir /absolute/path/to/project \
  --confirmed \
  --api-key-env AI_GATEWAY_API_KEY \
  --parallel 2
```

The video stage writes:

```text
prompts/videos/*.prompt.txt
videos/*.mp4
logs/*.json
```

Validate final videos with `ffprobe`:

```bash
ffprobe -v error -select_streams v:0 \
  -show_entries stream=width,height,r_frame_rate,duration \
  -show_entries format=duration -of json /path/to/video.mp4

ffprobe -v error -select_streams a:0 \
  -show_entries stream=codec_name,channels,duration \
  -of json /path/to/video.mp4
```

Report whether output is 9:16, approximately the requested duration, and has an audio stream.

## Prompting Rules

For storyboard prompts:

- Treat product image(s) as the source of truth for shape, material, label placement, color, scale, and category.
- Convert the script into a clear visual planning sheet, not a final video.
- Keep storyboard labels short and readable.
- Preserve exact on-screen text only when the script provides it.
- Avoid fake claims, fake numbers, fake certifications, fake logos, and unrelated products.

For video prompts:

- Treat the storyboard as reference content, not as the final screen layout.
- Do not restate the storyboard as detailed timestamped shot descriptions in the video prompt. The storyboard image already carries the action and composition; the video prompt should only add global execution constraints.
- Keep the product constraint concise by default: `严格参考故事版左上角产品部分。`
- When the user requests subtitles or voiceover, allow them and use only the storyboard's key copy. Prefer a natural female voiceover for beauty/skincare ads when requested.
- Explicitly prohibit reproducing storyboard grids, panel numbers, tables, tiny labels, watermarks, or UI.
- Keep output 9:16 vertical unless the user asks otherwise.
- Keep product consistency stronger than cinematic novelty.
- Use non-fast Seedance by default unless the user asks for fast draft mode.
- Include audio by default unless the user asks for silent output.

## Approval Gate

The approval gate is important because video generation spends more quota and is slower than storyboard generation.

Use this policy:

- If the user asks to generate a storyboard, stop after storyboards and ask for confirmation.
- If the user says "OK", "确认", "故事版可以", "继续生成视频", or equivalent, run the video stage.
- If the user asks to revise the storyboard, rerun only the storyboard stage or manually adjust prompts first.
- If the user asks to skip confirmation and generate everything in one go, state that this skill is designed as a two-stage workflow, then proceed only if the instruction is explicit and recent.

The orchestration script enforces this in normal execution: `video` requires `--confirmed` unless `--dry-run` is used.

## Error Handling

- **API key missing:** run `configure_ai_gateway.py`, set `AI_GATEWAY_API_KEY`, or pass a legacy key variable.
- **Base URL missing:** run `configure_ai_gateway.py`, set `AI_GATEWAY_BASE_URL`, or pass `--base-url`.
- **Wrong base URL:** use the root OpenAI-compatible URL expected by the wrapper, not a full operation endpoint.
- **Provider mismatch:** model IDs and request fields differ across gateways. Start with `--dry-run`, compare the payload with provider documentation, and use `--metadata` or `--extra` only for documented fields.
- **Storyboard product drift:** add stricter `--product-notes` and regenerate the storyboard.
- **Video includes storyboard UI:** strengthen the video prompt to say the storyboard is reference only and must not appear as grid, panels, labels, or table.
- **Video not 9:16:** verify `--width 720 --height 1280 --ratio 9:16`.
- **No audio:** verify the video command includes `--generate-audio`.
- **Long video:** split into 15s segments, generate multiple clips, then stitch externally if the user requests a single final video.

## Output Response

After storyboard generation, respond with:

- project directory
- generated storyboard image paths and inline previews
- prompt path(s)
- a clear request for approval

After video generation, respond with:

- generated video paths and inline previews
- model used
- ffprobe verification for ratio, duration, fps, and audio
- any failed segment and next action
