---
name: script-to-storyboard-video
description: Turn an existing advertising script plus product images into storyboard sheets, stop for explicit human approval, then generate vertical ad clips through AI Creative MCP. Use when the user already has an ad script or explicitly requests a storyboard-first approval workflow. Do not use for creator-persona development, character-reference generation, continuous keyframes, or character-led UGC; use product-to-ugc-video for those requests.
---

# Script To Storyboard Video

This skill turns an advertising script plus product image(s) into a staged production package:

1. **Storyboard stage:** generate one or more storyboard sheets from the script, product image, and target duration using the configured image model.
2. **Approval gate:** stop and show the storyboard(s). Do not generate video until the user explicitly confirms the storyboard is OK.
3. **Video stage:** use the approved storyboard sheet(s) as visual references and call AI Creative MCP to generate 9:16 clips with audio.

It is intentionally narrower than `product-to-ugc-video`: it does not build a creator persona, character sheet, or adjacent-frame UGC plan. It is for ad storyboard production and direct compatible video execution.

## Bundled Scripts

The skill includes self-contained provider wrappers:

- `scripts/image_tool.py`: AI Creative MCP image/reference generation runtime.
- `scripts/generate_video.py`: AI Creative MCP task submission, polling and result download.
- `scripts/script_to_storyboard_video.py`: thin orchestration layer for this skill's two-stage workflow.
- `scripts/aicreative_mcp.py`: MCP configuration, model discovery and local reference bindings.

The vendored provider wrappers are generated from the repository's `shared/media-runtime/` source so this skill remains independently installable without maintaining divergent copies.

Read this file first. Only open script source if you need to debug parameters or patch behavior.

## MCP setup

Read [references/aicreative-mcp.md](references/aicreative-mcp.md) for authentication, local image bindings, model discovery and task recovery. Use Python 3.11+, Pillow and ffprobe. Existing Codex `aicreative` configuration is reused without copying the Token. Bind local product images before generation; generated storyboards reuse returned asset IDs automatically.

## Inputs

Collect or infer:

- ad script text or a script file
- one or more product image paths
- target total duration
- desired output language for storyboard labels
- optional product notes, compliance constraints, aspect ratio, segment duration

Defaults:

- storyboard model: `AICREATIVE_IMAGE_MODEL_ID` or `2102` (Seedream 4.5)
- storyboard canvas hint: `2048x1152`; actual dimensions follow the model tier
- storyboard sheet aspect: `16:9`
- video model: `AICREATIVE_VIDEO_MODEL_ID` or `1103` (Seedance 2.0)
- video output: `9:16`, `720P`, audio on; verify actual output dimensions
- maximum segment duration: `15s`; balanced splitting avoids a trailing clip shorter than the default model minimum of 4 seconds

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
  --project-name body-oil-cream-ad
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

## Recovery and capability limits

Use `--project-dir` on the storyboard command to resume the same project; video uses the existing `--project-dir`. Journals preserve task IDs and completed artifacts. Changed prompts/models require a new project instead of overwriting approved work. `--dry-run` is offline.

The selected model must support the requested duration, ratio, resolution and audio mode. The runtime checks live model definitions before creating tasks. A storyboard is a general image reference, not a first-frame constraint. Video prompts must still prohibit storyboard grids and labels. The MCP exposes no watermark switch; `no watermark` is a semantic prompt instruction, not a guaranteed postprocessing control.

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
