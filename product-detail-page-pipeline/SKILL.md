---
name: product-detail-page-pipeline
description: Build a complete product-detail-page image workflow from product facts, buyer concerns, optional competitor references, and platform requirements. Use whenever the user wants Amazon A+ images, Shopify product-page visuals, TikTok Shop or Taobao/Tmall detail images, a coherent multi-image listing set, or a reusable production pipeline that requires per-page review and explicit user approval before generating each screen separately with model-rendered copy, preserving every original screen, and locally stitching the screens into a long page.
---

# Product Detail Page Pipeline

Build a coherent detail-page image set as a production workflow. Start with the shopper's decision, not decoration: every screen should answer one buyer question with visible evidence.

Planning works without external services. Offline generation orchestration requires Python 3.11+. Local contact-sheet and long-page assembly require Pillow. Real generation uses the bundled AI Creative MCP client. Read [references/aicreative-mcp.md](references/aicreative-mcp.md) for configuration, local source-image bindings and recovery.

## 积分确认门禁（必须执行）

正式提交任何新的 AI Creative 生成任务前，先准备提示词、素材和参数，运行下方的正常生成命令。未确认时运行器只读取模型配置、写出 `*.credits.json` 和配套 `.md`，随后以 `Credit approval required` 停止，不会提交生成任务。

按所选页面整批汇总；保留逐页内容审阅和原有生图确认，内容确认不能替代积分确认。

向用户说明本批次内容、模型和数量，并告知：**“大约需要消耗 xx 积分”**。xx 使用当前模型 `minPoints × 生成数量` 累加；补充“按模型起步积分估算，实际扣费可能随参数变化”。不得称为准确报价或扣费上限。读取不到起步积分时停止，不猜测免费或沿用硬编码价格。

等待用户明确同意本次已告知的预估后，才可用 `scripts/aicreative_mcp.py approve-credits --review <本次确认文件> --confirmation '<用户实际回复>'` 记录同意，并重跑原命令。不能自行确认，也不能把历史的“不限积分”、生成请求或内容审阅当作对本次积分的确认。用户拒绝或未回复时不提交。

任务数量、模型、提示词、素材、参数（含时长、分辨率、声音、公开开关）或账户变化，需要重新告知并确认。已获批任务的同一 `clientRequestId` 重试，以及查询、下载已有任务无需重复确认；新增任务和失败后的重新生成仍需确认。禁止通过直接调用 MCP `submit_generation_task`、改用其他脚本或自行写入确认文件绕过门禁。纯规划和 `--dry-run` 不收费、不需要确认。详细操作见 [MCP 积分门禁](references/aicreative-mcp.md#credit-approval-gate)。

## Boundary

Use this skill for multi-screen product-detail storytelling. For a single clean marketplace product image, use `standard-product-image`. For ad campaign planning or video, hand the completed product evidence to the relevant downstream skill.

## Inputs

Collect or infer:

- product name, category, visible facts, materials/specs, colors, source images;
- verified selling points, target buyer, price position, usage context;
- target platform, language, screen count, aspect ratio and text density;
- brand palette/style and elements to avoid;
- optional competitor links or images;
- image backend capabilities only when actual generation is requested.

Record assumptions. Treat source images and supplied specifications as evidence; do not turn marketing adjectives into facts.

Read `references/platform-presets.md` when the target platform is known. Read `references/compliance.md` before writing claims, comparisons, badges, before/after content, health/beauty copy, or regulated-product copy.

## Workflow

### 1. Product evidence

Create `01_product_profile.json` using `references/schemas.md`:

- separate visible facts, supplied facts and unsupported claims;
- rank selling points by buyer relevance and proof strength;
- record must-show and must-not-distort product attributes;
- discard or quarantine claims that lack evidence.

### 2. Buyer concerns

Create `02_buyer_concerns.json`. Translate each viable selling point into a shopper question, such as:

- Will it fit my use case?
- What proves the material or construction quality?
- How large, compatible, maintainable or easy to install is it?
- Why choose this rather than the common alternative?
- What arrives in the package?

Give each concern a proof type, priority, evidence source and risk if unproven.

### 3. Competitor decisions, optional

Create `03_competitor_brief.json` with `adopt`, `improve` and `differentiate`. Describe patterns at the strategy level. Do not copy a competitor's protected artwork, exact layout, text, photography or brand identity.

### 4. Screen plan

Create `04_screen_plan.json`. Use 6–10 screens unless the user specifies otherwise. Each screen needs:

- one buyer question;
- one commercial role;
- visible proof and its evidence source;
- headline/subheadline limits;
- a measurable success criterion.

Avoid multiple screens that repeat the same claim with different decoration.

### 5. Shared visual system

Create `05_visual_dna.json` and `06_photography_plan.json`:

- palette, typography hierarchy, lighting, background materials and negative rules;
- stable product color/material rendering and reference policy;
- per-screen framing, angle, depth of field, props and product state.

Keep constants shared across the set while varying screen-specific composition.

### 6. Prompt pack

Create `07_prompt_pack.json` using `references/schemas.md`. Every screen must include:

- final prompt and negative prompt;
- exact customer-facing copy to render directly inside that screen;
- copy language, hierarchy, placement, typography direction and line limits;
- buyer question and visible proof target;
- aspect ratio, size, reference images and assembly plan.

Keep text concise enough for reliable model rendering. Quote every required string and instruct the model to reproduce it verbatim without translation, paraphrase, spelling changes or extra words. Generate one complete screen per call; do not ask the model to create the entire long page in one image.

### 7. Aspect-ratio plan

Treat the final long page ratio as an assembly result, never as a request for one model-generated image. Choose a supported ratio and common pixel width for each screen, generate every screen independently, and let the total height emerge from local vertical assembly.

When a requested screen ratio is unsupported, run:

```bash
python3 scripts/aspect_ratio_plan.py \
  --target-ratio 1:2.7 \
  --supported-ratios 1:1,4:5,3:4,2:3,9:16,1:4
```

Use direct generation or a safe-area crop when the mismatch is small. For an extreme ratio, redesign it as multiple self-contained modules, generate each module independently at a supported ratio, preserve each original, and stack them locally. Do not create overlapping fragments of one canvas. Never stretch the product or ask the model for the complete long page.

### 8. Mandatory per-page review

Before any real image-model call, export a review package that lists every page's buyer question, visual content, exact customer-facing copy, text layout, evidence, prohibited claims, canvas and references:

```bash
python3 scripts/prepare_generation_review.py \
  --prompt-pack 07_prompt_pack.json \
  --output-dir generation_review
```

Show the complete `generation_review.md` content to the user. Ask them to approve or request changes by page number. Do not summarize away page details, create an approval file, call an image model, or continue automatically.

If the user changes any page, update `07_prompt_pack.json`, regenerate the review and show all pages again. Stop and wait until the user explicitly says `开始生图`, `确认生图`, `Start image generation`, or another equally explicit instruction to begin image generation. A general acknowledgment such as “可以”, “继续”, or “looks good” is not generation approval.

### 9. Record explicit approval

Only after receiving explicit generation approval, bind it to the exact reviewed Prompt Pack:

```bash
python3 scripts/record_generation_approval.py \
  --prompt-pack 07_prompt_pack.json \
  --review generation_review/generation_review.json \
  --output generation_review/generation_approval.json \
  --confirmation "开始生图"
```

When the user explicitly approves only selected pages, record and execute the same scope:

```bash
python3 scripts/record_generation_approval.py \
  --prompt-pack 07_prompt_pack.json \
  --review generation_review/generation_review.json \
  --output generation_review/generation_approval.json \
  --confirmation "开始生1-3图" \
  --only-screen 1 --only-screen 2 --only-screen 3

python3 scripts/run_image_generation.py \
  --prompt-pack 07_prompt_pack.json \
  --output-dir generated \
  --approval-file generation_review/generation_approval.json \
  --only-screen 1 --only-screen 2 --only-screen 3
```

Never create this file preemptively. Any Prompt Pack edit changes its SHA-256 and invalidates the approval; export and show a new review, then ask for explicit approval again.

### 10. Per-screen generation

Use dry-run before spending quota; dry-run never counts as approval and makes no provider call:

```bash
python3 scripts/run_image_generation.py \
  --prompt-pack 07_prompt_pack.json \
  --output-dir generated \
  --dry-run
```

Reuse the configured AI Creative MCP server and bind source references before generation:

```bash
python3 scripts/aicreative_mcp.py check
python3 scripts/check_image_backend.py --operation generate --operation edit --size 1024x1536
```

Then run generation with the bundled image client:

```bash
python3 scripts/run_image_generation.py \
  --prompt-pack 07_prompt_pack.json \
  --output-dir generated \
  --approval-file generation_review/generation_approval.json
```

The runner refuses real generation without a current approval file. It reads the configured MCP server and `AICREATIVE_IMAGE_MODEL_ID`, chooses `edit` when local references resolve and `generate` otherwise, and performs a non-generating backend preflight before a real run. Its manifest records the approval, sanitized preflight, missing references, commands, return codes and expected outputs. Use `--model` for the numeric modelConfigId. `--size` and `--supported-sizes` describe allowed canvas ratio hints, not exact output pixels; actual dimensions follow model resolution tiers. Original server bytes are preserved beside delivery PNGs as `*.original`. Do not replace the MCP tool with a gateway client.

Keep reference paths relative to the Prompt Pack directory whenever possible. To authorize images outside that directory, pass their containing directory with `--reference-dir`; absolute paths in the Prompt Pack are rejected unless they resolve inside an explicitly authorized reference directory. Missing, non-image, symlinked or out-of-root references block real generation.

For a real run, call the image backend separately for every screen. Save the returned complete screen images under `generated/images/screen_XX.*`. These are final original deliverables, not temporary clean plates.

### 11. Local assembly

After all independently generated screens exist, assemble them locally without adding or changing text:

```bash
python3 scripts/assemble_detail_page.py \
  --prompt-pack 07_prompt_pack.json \
  --image-dir generated/images \
  --output-dir final_assembly
```

The assembler must not redraw, overlay or edit customer-facing copy. It validates the expected screen set, preserves the original image files, computes checksums, applies only prompt-planned center crops to assembly derivatives, and creates a contact sheet, a vertical long page and an assembly manifest. Deliver both `generated/images/` and `final_assembly/detail_page_long.*`.

### 12. QC

Create `08_qc_report.json` and reject a screen when:

- the product is deformed, recolored or missing important components;
- the claimed evidence is not actually visible;
- copy exceeds supplied evidence or platform-safe language;
- model-rendered text is misspelled, paraphrased, unreadable, cropped or inconsistent with the exact prompt copy;
- the set lacks narrative coverage or visual consistency;
- competitor expression has been copied too closely.

## Output

Planning output:

```text
01_product_profile.json
02_buyer_concerns.json
03_competitor_brief.json        # optional
04_screen_plan.json
05_visual_dna.json
06_photography_plan.json
07_prompt_pack.json
08_qc_report.json
```

Execution output adds the generation manifest, every original independently generated screen, the assembly manifest, a contact sheet and the stitched long page.

```text
generated/
├── generation_manifest.json
└── images/
    ├── screen_01.png
    ├── screen_02.png
    └── ...                         # all delivered originals
final_assembly/
├── assembly_manifest.json
├── contact_sheet.png
└── detail_page_long.png
generation_review/
├── generation_review.json
├── generation_review.md
└── generation_approval.json       # only after explicit user approval
```

## Operating Rules

- Keep visible fact, user-supplied fact and inference distinguishable.
- Do not invent certification, performance, compatibility, warranty, reviews or package contents.
- Use only product and competitor assets the user is authorized to process.
- Preserve missing-reference and failed-screen states rather than silently substituting unrelated images.
- In the approval-bound runner, use `--extra` only for a documented deterministic `seed`; core request fields and unknown extras are rejected.
- Always show every planned page and wait for explicit generation approval before any real image-model call.
- Treat plan changes as approval-invalidating changes; never reuse an approval for a modified Prompt Pack.
- Never interpret `继续`, `可以`, `OK`, silence or a request to adjust pages as permission to generate images.
- Never repair model text with CSS, HTML, SVG, Pillow drawing or another text-overlay layer. Regenerate only the failed screen with a shorter copy or stricter verbatim text instruction.
- Never generate the complete detail page as one image. Generate screens independently, then stitch locally.
- Never discard or overwrite original screen images during assembly.
- If a paid retry is only aesthetic, tell the user and let them choose.

Run `python3 tests/test_smoke.py` for offline verification.
