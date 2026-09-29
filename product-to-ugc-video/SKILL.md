---
name: product-to-ugc-video
description: Turn a product image plus product description into a character-led UGC video project with a stable creator persona, character reference, continuous keyframes, adjacent-frame video segments, and merge metadata. Use when character identity and scene continuity are the core requirement. Do not use when the user already has an ad script and wants storyboard sheets reviewed before video generation; use script-to-storyboard-video for that workflow.
---

# Product To UGC Video

## 积分确认门禁（必须执行）

正式提交任何新的 AI Creative 生成任务前，先准备提示词、素材和参数，运行下方的正常生成命令。未确认时运行器只读取模型配置、写出 `*.credits.json` 和配套 `.md`，随后以 `Credit approval required` 停止，不会提交生成任务。

在第一张人物参考图提交前，汇总人物图、全部关键帧和视频片段的预估；已有或明确跳过的任务不计入新增预估。

向用户说明本批次内容、模型和数量，并告知：**“大约需要消耗 xx 积分”**。xx 使用当前模型 `minPoints × 生成数量` 累加；补充“按模型起步积分估算，实际扣费可能随参数变化”。不得称为准确报价或扣费上限。读取不到起步积分时停止，不猜测免费或沿用硬编码价格。

等待用户明确同意本次已告知的预估后，才可用 `scripts/aicreative_mcp.py approve-credits --review <本次确认文件> --confirmation '<用户实际回复>'` 记录同意，并重跑原命令。不能自行确认，也不能把历史的“不限积分”、生成请求或内容审阅当作对本次积分的确认。用户拒绝或未回复时不提交。

任务数量、模型、提示词、素材、参数（含时长、分辨率、声音、公开开关）或账户变化，需要重新告知并确认。已获批任务的同一 `clientRequestId` 重试，以及查询、下载已有任务无需重复确认；新增任务和失败后的重新生成仍需确认。禁止通过直接调用 MCP `submit_generation_task`、改用其他脚本或自行写入确认文件绕过门禁。纯规划和 `--dry-run` 不收费、不需要确认。详细操作见 [MCP 积分门禁](references/aicreative-mcp.md#credit-approval-gate)。

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
5. Generate AI Creative MCP video segments through `scripts/generate_video.py` using adjacent frames as first and last anchors.
6. Save an assembly manifest and merge metadata for final stitching.

## AI Creative MCP backend

Read [references/aicreative-mcp.md](references/aicreative-mcp.md) for authentication, bindings and recovery. Use Python 3.11+ and Pillow; use ffmpeg/ffprobe for video assembly and validation. The default image/video model IDs are 2102/1108 (Seedream 4.5 / Wan 2.7), overridable with `AICREATIVE_IMAGE_MODEL_ID` / `AICREATIVE_VIDEO_MODEL_ID`. Character-led UGC requires both person-reference and first/last-frame support. Seedance 2.0 rejected realistic generated faces in Beta testing. The runner checks compatibility before generating any images. Wan 2.7 requires native audio ON; `--no-generate-audio` is available only with a model that supports OFF.

Bind the local product image and any supplied character reference to matching AI Creative assets first. Generated character references and frames are automatically reused by asset ID. Keyframe images use product + character + previous-frame references. Videos pass adjacent images explicitly as `frame.firstFrame` / `frame.lastFrame`, never as general `imageAssets` in the same request.

Keep keyframes at the requested video aspect ratio: the tested video backend can follow frame geometry instead of the requested output ratio. For phone-shot UGC, explicitly request a full-frame photograph without a phone device, bezel or screen UI. Inspect references and keyframes for these artifacts before using them in final production; image-generation success alone does not establish visual quality.

This branch does not use AI gateway settings or a text API. The calling agent creates the structured plan and passes `--plan-file`; use `--heuristic-plan` only for the deterministic local fallback. Keep the skill's product and creator continuity checks.

## Script Entry Point

Use:

```bash
python3 scripts/product_to_ugc.py --product-image ... --description ...
```

Read [references/cli.md](references/cli.md) for common command patterns and [references/project-layout.md](references/project-layout.md) for the output structure.

## Planner behavior

Prepare a JSON plan containing `creator_profile`, `character_reference_prompt`, `frames` and adjacent-frame `segments`. To inspect the required shape, run `--heuristic-plan --planner-only`, then refine the resulting `planning/plan.json` with the supplied product facts and creative brief. Pass that file with `--plan-file` for generation. The script validates the plan before creating media.

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
