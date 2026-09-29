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

## 积分确认与连接选择

优先使用当前会话已连接的 AI Creative MCP 工具。平台连接与 Python CLI 的本地配置是两个独立入口：原生 `list_models` 成功即可继续读取模型参数和准备任务，不需要先运行 CLI `check`，也不需要向用户索要 Token。CLI 报“未配置”不代表平台未授权；有原生工具时直接走原生路径，不要求平台把凭证交给脚本。

提交前说明本批次内容、模型、数量及关键参数，并告知 **“大约需要消耗 xx 积分”**；xx = 当前模型 `minPoints × 本批新增生成数量` 之和，注明“按模型起步积分估算，实际扣费可能随参数变化”。从原生 `list_models` / `get_model_parameters` 或 CLI 读取起步积分；缺失时只补查该信息，不编造价格。

用户明确同意已展示的本批次方案及预计积分后即可提交。原生路径允许直接调用 `submit_generation_task`，会话中的确认就是依据，不要求 `*.credits.json`、`approve-credits` 或 CLI 连通性检查。把估算、实际回复及任务 ID 记录在现有项目日志即可，不新增专用凭证审批。CLI 路径仍用 `approve-credits` 记录同一条用户回复，不再为生成确认文件询问用户。

故事板与视频分别估算；正式故事板仍须经用户审阅后再生成视频。展示故事板时可以一并告知视频积分，让用户一次确认内容和费用。

同一批次、同一账户、同一费用范围内，切换原生/CLI、修复连接、整理输出路径或等义润色提示词不需要重复确认。新增付费任务、变更模型/数量/计费参数或提高预估时，再告知变化并确认；内容、素材、公开范围的实质变化按用户要求确认。已接受的任务只查询或下载，提交结果不明时保留同一 `clientRequestId`，不另建任务。只读查询、规划与离线预览无需积分确认。用户未同意或拒绝时不提交；连接授权、过去的“不限积分”不替代本批次费用同意。详细操作见 [原生 MCP 与积分确认](references/aicreative-mcp.md#credit-approval-gate)。

## Bundled Scripts

The optional CLI path includes self-contained provider wrappers. Platform-native MCP execution does not require these wrappers to connect:

- `scripts/image_tool.py`: AI Creative MCP image/reference generation runtime.
- `scripts/generate_video.py`: AI Creative MCP task submission, polling and result download.
- `scripts/script_to_storyboard_video.py`: thin orchestration layer for this skill's two-stage workflow.
- `scripts/aicreative_mcp.py`: MCP configuration, model discovery and local reference bindings.

The vendored provider wrappers are generated from the repository's `shared/media-runtime/` source so this skill remains independently installable without maintaining divergent copies.

Read this file first. Only open script source if you need to debug parameters or patch behavior.

## MCP setup

Read [references/aicreative-mcp.md](references/aicreative-mcp.md) for native execution, optional CLI setup, references and task recovery. Prefer the platform MCP connection; resolve product references to asset IDs there and reuse generated storyboard asset IDs for videos. Python 3.11+ and Pillow are needed for local scripts; ffprobe verifies final videos. A CLI configuration failure does not block native execution.

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

With platform tools, reuse any prepared project/prompts and submit one IMAGE job per sheet after credit confirmation. A prepared local preview is not a completed generated storyboard. Keep the generated sheet, its asset ID and task log per segment; show those actual results for review.

The optional `storyboard` CLI writes the project and prompts with `--dry-run` without credentials. You may use those files for native submissions, then update the segment output paths and logs. Do not rerun the real CLI after native submission. With CLI configuration, run the subcommand normally. Both paths preserve:

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

After the storyboard tasks finish:

1. Show the generated storyboard image(s) inline.
2. Give the `project_dir`.
3. Ask the user to confirm or request changes.
4. Do not proceed to video generation unless the user explicitly confirms.

## Stage 2: Generate Videos

After storyboard and video-credit approval, use the approved sheet asset ID as `imageAssets` in one native VIDEO job per segment; do not use the whole storyboard grid as a first frame. Build prompts using the rules below, then poll and save clips in the same project. A missing `--confirmed` flag or CLI receipt is not a native-path blocker; the actual user approval is required.

For configured CLI execution, use the `video` subcommand with `--confirmed`. It reads `project.json`, creates video prompts, and generates one clip per approved segment. It can also prepare prompts offline with `--dry-run`.

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
- If the user approves the storyboard, show the video estimate if not already approved. When storyboard review and video estimate were shown together, one clear reply may approve both; do not add a second confirmation just for bookkeeping.
- If the user asks to revise the storyboard, rerun only the storyboard stage or manually adjust prompts first.
- If the user asks to skip confirmation and generate everything in one go, state that this skill is designed as a two-stage workflow, then proceed only if the instruction is explicit and recent.

For CLI execution, `video` requires `--confirmed` unless `--dry-run` is used. For native tools, keep the same storyboard review boundary using the conversation approval.

## Recovery and capability limits

Keep the existing project, prompts, generated sheets and task IDs when repairing a connection. Native execution resumes by task ID; do not repeat accepted jobs. For CLI execution, use `--project-dir` to resume and retain its journals. New paid generations use new job IDs/output files; preserve the approved originals. `--dry-run` is offline.

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
