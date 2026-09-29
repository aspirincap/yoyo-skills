---
name: product-to-ugc-video
description: Turn a product image plus product description into a character-led UGC video project with a stable creator persona, character reference, continuous keyframes, adjacent-frame video segments, and merge metadata. Use when character identity and scene continuity are the core requirement. Do not use when the user already has an ad script and wants storyboard sheets reviewed before video generation; use script-to-storyboard-video for that workflow.
---

# Product To UGC Video

## 积分确认与连接选择

优先使用当前会话已连接的 AI Creative MCP 工具。平台连接与 Python CLI 的本地配置是两个独立入口：原生 `list_models` 成功即可继续读取模型参数和准备任务，不需要先运行 CLI `check`，也不需要向用户索要 Token。CLI 报“未配置”不代表平台未授权；有原生工具时直接走原生路径，不要求平台把凭证交给脚本。

提交前说明本批次内容、模型、数量及关键参数，并告知 **“大约需要消耗 xx 积分”**；xx = 当前模型 `minPoints × 本批新增生成数量` 之和，注明“按模型起步积分估算，实际扣费可能随参数变化”。从原生 `list_models` / `get_model_parameters` 或 CLI 读取起步积分；缺失时只补查该信息，不编造价格。

用户明确同意已展示的本批次方案及预计积分后即可提交。原生路径允许直接调用 `submit_generation_task`，会话中的确认就是依据，不要求 `*.credits.json`、`approve-credits` 或 CLI 连通性检查。把估算、实际回复及任务 ID 记录在现有项目日志即可，不新增专用凭证审批。CLI 路径仍用 `approve-credits` 记录同一条用户回复，不再为生成确认文件询问用户。

在第一张人物参考图提交前，汇总人物图、关键帧和视频片段的预计积分；已有或明确跳过的任务不计入新增预估。

同一批次、同一账户、同一费用范围内，切换原生/CLI、修复连接、整理输出路径或等义润色提示词不需要重复确认。新增付费任务、变更模型/数量/计费参数或提高预估时，再告知变化并确认；内容、素材、公开范围的实质变化按用户要求确认。已接受的任务只查询或下载，提交结果不明时保留同一 `clientRequestId`，不另建任务。只读查询、规划与离线预览无需积分确认。用户未同意或拒绝时不提交；连接授权、过去的“不限积分”不替代本批次费用同意。详细操作见 [原生 MCP 与积分确认](references/aicreative-mcp.md#credit-approval-gate)。

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

If the user only wants a conceptual plan, you can stop after the planning outputs. If the user wants generated assets, prefer native MCP execution below; `scripts/product_to_ugc.py` is the optional configured CLI path.

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
4. Generate continuous keyframes through native MCP IMAGE jobs or the configured `scripts/image_tool.py`.
5. Generate native MCP VIDEO jobs or use the configured `scripts/generate_video.py`, with adjacent frames as first and last anchors.
6. Save an assembly manifest and merge metadata for final stitching.

## AI Creative MCP backend

Read [references/aicreative-mcp.md](references/aicreative-mcp.md) for native execution, optional CLI setup, references and recovery. Prefer platform tools; no CLI connection check or credit receipt is required for native submissions. Use Python 3.11+ and Pillow; use ffmpeg/ffprobe for video assembly and validation. The default image/video model IDs are 2102/1108 (Seedream 4.5 / Wan 2.7), overridable with `AICREATIVE_IMAGE_MODEL_ID` / `AICREATIVE_VIDEO_MODEL_ID`. Character-led UGC requires both person-reference and first/last-frame support. Seedance 2.0 rejected realistic generated faces in Beta testing. On either path, check the video model compatibility before generating any images. Wan 2.7 requires native audio ON; `--no-generate-audio` is available only with a model that supports OFF.

Resolve the product image and any supplied character reference to matching AI Creative asset IDs through the chosen connection (CLI users bind local files). Generated character references and frames are automatically reused by asset ID. Keyframe images use product + character + previous-frame references. Videos pass adjacent images explicitly as `frame.firstFrame` / `frame.lastFrame`, never as general `imageAssets` in the same request.

Keep keyframes at the requested video aspect ratio: the tested video backend can follow frame geometry instead of the requested output ratio. For phone-shot UGC, explicitly request a full-frame photograph without a phone device, bezel or screen UI. Inspect references and keyframes for these artifacts before using them in final production; image-generation success alone does not establish visual quality.

This branch does not use AI gateway settings or a text API. The calling agent creates the structured plan and passes `--plan-file`; use `--heuristic-plan` only for the deterministic local fallback. Keep the skill's product and creator continuity checks.

## Native execution and optional CLI

For native execution, prepare the plan and project structure below; `--planner-only` / `--dry-run` can scaffold them offline without credentials. Quote the full new chain once, obtain agreement, then submit in dependency order: character IMAGE → keyframe IMAGE jobs → adjacent-frame VIDEO jobs. Inspect each generated reference before using its asset ID downstream. Keep all task IDs, files, assembly/merge manifests and timing records in the project. Do not rerun the submitting CLI over native results.

For configured CLI execution, use:

```bash
python3 scripts/product_to_ugc.py --product-image ... --description ...
```

Read [references/cli.md](references/cli.md) for common command patterns and [references/project-layout.md](references/project-layout.md) for the output structure.

## Planner behavior

Prepare a JSON plan containing `creator_profile`, `character_reference_prompt`, `frames` and adjacent-frame `segments`. To inspect the required shape, run `--heuristic-plan --planner-only`, then refine the resulting `planning/plan.json` with the supplied product facts and creative brief. Use this plan directly with native MCP, or pass it with `--plan-file` to the configured CLI. The script can validate it offline before creating media.

Do not silently replace the agent's creative plan with the heuristic fallback. The latter is an explicit offline planning option.

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

- Use the configured AI Creative MCP endpoint and model IDs available to the account; do not fall back to a gateway.
- Preserve visible product structure, label placement, color, and usage. Do not invent certifications, results, reviews, or before/after claims.
- Start with `--heuristic-plan --dry-run` to inspect prompts and manifests without spending quota.
- Treat customer images, generated faces, API responses, and project folders as private unless redistribution rights are clear.
- Preserve successful assets when retrying a failed segment; do not regenerate the entire project without a reason.
