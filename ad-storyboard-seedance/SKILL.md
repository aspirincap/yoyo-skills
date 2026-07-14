---
name: ad-storyboard-seedance
description: Create a two-stage commercial video workflow from an ad script, product image, and target duration: first generate storyboard sheets for review, then only after explicit approval call a configurable OpenAI-compatible Seedance video provider to produce vertical clips. Use whenever the user asks to turn an ad script or product image into storyboards, approve a storyboard before paid video generation, or build a repeatable storyboard-to-video pipeline.
license: MIT
compatibility: Python 3.10+, an OpenAI-compatible image endpoint, and a compatible asynchronous video generation endpoint; ffprobe is optional for output verification.
---

# Ad Storyboard To Seedance

This skill turns an advertising script plus product image(s) into a staged production package:

1. **Storyboard stage:** generate one or more storyboard sheets from the script, product image, and target duration using the configured image model.
2. **Approval gate:** stop and show the storyboard(s). Do not generate video until the user explicitly confirms the storyboard is OK.
3. **Seedance stage:** use the approved storyboard sheet(s) as visual references and call the configured compatible video endpoint to generate 9:16 clips with audio.

It is intentionally narrower than `product-to-ugc-video`: it does not build a creator persona, character sheet, or adjacent-frame UGC plan. It is for ad storyboard production and direct Seedance execution.

## Bundled Scripts

The skill includes self-contained provider wrappers:

- `scripts/image_tool.py`: OpenAI-format image generation/editing used for storyboards.
- `scripts/generate_video.py`: configurable `/v1/video/generations` wrapper. Provider-specific fields may require `--extra` or `--metadata`.
- `scripts/ad_storyboard_pipeline.py`: thin orchestration layer for this skill's two-stage workflow.

Read this file first. Only open script source if you need to debug parameters or patch behavior.

## Environment

This skill has its own env template at `.env.example`. From the skill directory, copy it to `.env` and fill in the base URL, model IDs, and one API key. Never commit the resulting `.env`.

The scripts automatically load:

1. the file pointed to by `AD_STORYBOARD_SEEDANCE_ENV_FILE`, if set
2. the skill-local `.env`, if present

Shell environment variables take priority over `.env` values. Never package or publish a real `.env` file.

Required base URL:

- `AD_STORYBOARD_BASE_URL`: OpenAI-compatible root URL, without `/v1/...`
- `AD_STORYBOARD_IMAGE_MODEL`: provider image model ID
- `AD_STORYBOARD_VIDEO_MODEL`: provider Seedance model ID

Optional modality-specific overrides:

- `IMAGE_API_BASE_URL`
- `VIDEO_API_BASE_URL`

## Inputs

Collect or infer:

- ad script text or a script file
- one or more product image paths
- target total duration
- desired output language for storyboard labels
- optional product notes, compliance constraints, aspect ratio, segment duration

Defaults:

- storyboard model: `AD_STORYBOARD_IMAGE_MODEL` or `gpt-image-1`
- storyboard sheet size: `2048x1152`
- storyboard sheet aspect: `16:9`
- video model: `AD_STORYBOARD_VIDEO_MODEL`; configure a non-fast model when final quality matters
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
python3 scripts/ad_storyboard_pipeline.py storyboard \
  --script-file /absolute/path/script.txt \
  --product-image /absolute/path/product.png \
  --duration 30 \
  --project-name body-oil-cream-ad \
  --api-key-env OPENAI_API_KEY,NEWAPI_API_KEY
```

After the command finishes:

1. Show the generated storyboard image(s) inline.
2. Give the `project_dir`.
3. Ask the user to confirm or request changes.
4. Do not proceed to video generation unless the user explicitly confirms.

## Stage 2: Generate Seedance Videos

After approval, use the `video` subcommand with `--confirmed`. It reads `project.json`, creates video prompts, and generates one clip per approved storyboard segment.

Example:

```bash
python3 scripts/ad_storyboard_pipeline.py video \
  --project-dir /absolute/path/to/project \
  --confirmed \
  --api-key-env OPENAI_API_KEY,NEWAPI_API_KEY \
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

For Seedance prompts:

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

- **API key missing:** pass `--api-key-env OPENAI_API_KEY,NEWAPI_API_KEY` or configure one of those variables.
- **Base URL missing:** set `AD_STORYBOARD_BASE_URL` in the skill-local `.env`, export it in the shell, or pass `--base-url`.
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
