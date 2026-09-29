---
name: standard-product-image
description: "Create standardized ecommerce product image prompts, or generate standardized product images from real product photos. Use when the user provides product photos and asks to identify the product type, standardize 商品图/白底图/电商主图/产品图, or produce prompts for phones, fans, cookware, tableware, smartwatches, massage guns, or similar generic products."
license: MIT
---

# Standard Product Image

## 积分确认门禁（必须执行）

正式提交任何新的 AI Creative 生成任务前，先准备提示词、素材和参数，运行下方的正常生成命令。未确认时运行器只读取模型配置、写出 `*.credits.json` 和配套 `.md`，随后以 `Credit approval required` 停止，不会提交生成任务。

按本次生成数量汇总；修正瑕疵而重新生成也需要新的积分确认。

向用户说明本批次内容、模型和数量，并告知：**“大约需要消耗 xx 积分”**。xx 使用当前模型 `minPoints × 生成数量` 累加；补充“按模型起步积分估算，实际扣费可能随参数变化”。不得称为准确报价或扣费上限。读取不到起步积分时停止，不猜测免费或沿用硬编码价格。

等待用户明确同意本次已告知的预估后，才可用 `scripts/aicreative_mcp.py approve-credits --review <本次确认文件> --confirmation '<用户实际回复>'` 记录同意，并重跑原命令。不能自行确认，也不能把历史的“不限积分”、生成请求或内容审阅当作对本次积分的确认。用户拒绝或未回复时不提交。

任务数量、模型、提示词、素材、参数（含时长、分辨率、声音、公开开关）或账户变化，需要重新告知并确认。已获批任务的同一 `clientRequestId` 重试，以及查询、下载已有任务无需重复确认；新增任务和失败后的重新生成仍需确认。禁止通过直接调用 MCP `submit_generation_task`、改用其他脚本或自行写入确认文件绕过门禁。纯规划和 `--dry-run` 不收费、不需要确认。详细操作见 [MCP 积分门禁](references/aicreative-mcp.md#credit-approval-gate)。

## Overview

Turn real product photos into standardized ecommerce product image prompts or generated images. The visual target is a premium white-background product image: centered, realistic, high-key lighting, true structure, no labels, no decorative scene, no infographic layout.

Prompt-only mode has no external dependency. Direct image generation requires an image-capable model or image-editing tool in the current environment.

## Workflow

1. Inspect the source image and identify the closest category: `phone`, `fan`, `cookware`, `tableware`, `smartwatch`, `massage-gun`, or `generic`.
2. Extract only product facts visible in the source image: product type, color, material, shape, logo placement, functional details, screen/display state, packaging if it is part of the product presentation.
3. Confirm the destination platform or requested canvas when the user supplied one. Otherwise use the portable default: square canvas, approximately 75-85% subject coverage, and enough safe margin for marketplace cropping.
4. Write a standardized prompt using the base specification and the matching category add-on.
5. If the user asks to generate the image, use this branch's AI Creative MCP runtime with the source photo as the reference. If the user asks only for the prompt, return the prompt.
6. When the product does not fit a listed category, use `generic` and borrow the closest category's composition logic without inventing unseen details.
7. Inspect the output against the acceptance checklist. Regenerate only when a material defect is visible and the user approves the new credit estimate.

## Output Format

When returning a prompt, use this compact structure:

```markdown
识别类型：<品类>
关键特征：<从源图提取的颜色、材质、形态、品牌/Logo、重要部件>

Prompt:
<完整生图/修图提示词>

Negative prompt:
<负面提示词>
```

When generating an image, also include the generated image and a one-line note describing the recognized category.

## Base Specification

Use this base prompt for every category:

```text
请基于用户提供的实拍产品图进行商品图标准化处理，生成符合电商平台规范的高质量白底商品图。

画布：使用用户或目标平台指定的尺寸；未指定时采用 1:1 正方形和模型支持的高清尺寸。纯白色背景 #FFFFFF，无渐变、无纹理、无环境道具。
构图：产品主体通常占画面约 75%-85%，根据产品长宽比调整，居中摆放，四周保留均匀安全边距，视觉重心稳定，保持真实透视和真实比例。
视角：优先 45 度三分之四视角（3/4 view），展示产品厚度、体积和关键结构；若源图为正面或组合陈列，保留其最能表达商品的主视角。
光影：左上 45 度柔光棚拍布光，高光细腻自然，底部仅保留统一、轻微、柔和的接触阴影，不要硬阴影或复杂反射。
色彩：白平衡统一为暖白/日光约 5500K，亮度通透，对比度自然，保留原商品颜色、材质、金属/玻璃/塑料/陶瓷质感。
真实性：不改变品牌 Logo、产品结构、比例、颜色和可见部件；不添加源图不存在的功能、按钮、孔位、图案、文字、配件或装饰元素。
输出：仅输出标准化后的单张商品图，不添加标题、卖点字、水印、边框、角标、说明卡、信息图排版、背景场景或额外包装；若源图中的包装/礼盒本身属于商品展示的一部分，可保留并标准化。
```

Use this negative prompt:

```text
不要生成海报、说明页、文字、Logo 改写、水印、边框、价格标签、人物手持、生活场景、桌面背景、彩色背景、强阴影、过度反光、卡通风、3D 玩具感、AI 伪细节、变形结构、错误比例、多余配件、源图不存在的包装或装饰。
```

## Category Add-Ons

Append one add-on to the base prompt.

### Phone

Use for phones and similar mobile devices.

```text
品类细化：手机类商品图。优先展示机身背面和正面屏幕的组合陈列；背面略靠左或后方，正面略靠右或前方，轻微重叠但不遮挡摄像头和屏幕主体。保留摄像头模组、边框厚度、按键、品牌 Logo 和真实机身颜色。屏幕可保持源图屏幕内容；若源图屏幕不可用，使用简洁无文字的柔和抽象渐变，不添加 App 图标或营销文案。
```

### Fan

Use for desktop fans, air circulators, portable fans, and bladeless fans.

```text
品类细化：风扇类商品图。突出前网罩、扇叶、机头、支架、底座和控制按钮的层次；保持网格密度、叶片数量感、金属/塑料边圈和装饰色不变。采用略高于平视的 3/4 角度，让圆形风罩和底座稳定居中，白色或浅色材质要有清晰边缘与柔和阴影。
```

### Cookware

Use for pots, pans, lids, bakeware, kettles, and similar kitchen cookware.

```text
品类细化：锅具类商品图。突出锅身体积、锅口椭圆透视、锅盖、把手、旋钮、金属包边和釉面/不粘/不锈钢材质。锅体水平居中，保留真实高度和直径比例；金属件保持柔和高光，陶瓷或涂层表面保持真实纹理。不要添加食材、蒸汽、厨房台面或烹饪场景。
```

### Tableware

Use for bowls, plates, cups, cutlery sets, tea sets, boxed tableware, and gift-box tableware.

```text
品类细化：餐具类商品图。保留源图中的套装数量、盘碗杯位置关系、礼盒/收纳盒结构和内衬颜色；如果源图是礼盒套装，采用俯视偏 45 度的 3/4 展示，让盒内分区和餐具层次清晰。陶瓷保持洁白、细腻、低反光，金边或纹样必须与源图一致。不要新增餐具件数、餐桌布景、食物或装饰花草。
```

### Smartwatch

Use for smartwatches, watch bands, fitness trackers, and similar wearables.

```text
品类细化：智能手表类商品图。展示表壳、屏幕玻璃、表冠/按钮、传感器和表带弯曲形态；优先使用表盘正面偏 3/4 角度，表带自然环绕并保持真实厚度。屏幕内容保持源图；若源图不可用，使用简洁无文字的极简表盘或柔和抽象表盘，不添加 App 界面、通知文字或不存在的刻度。
```

### Massage Gun

Use for fascia guns, massage guns, handheld massagers, and similar wellness electronics.

```text
品类细化：筋膜枪类商品图。突出 T 形机身、按摩头、前端连接件、握柄、按钮、指示灯和金属/磨砂塑料质感。机身保持竖直或轻微倾斜，按摩头朝左前方或源图方向，确保圆形按摩头、横向电机仓和握柄比例真实。不要新增替换头、收纳盒、人物手持或健身场景。
```

### Generic

Use for all unmatched products.

```text
品类细化：通用电商商品图。识别源图最接近的商品结构类型：块状、圆柱、瓶罐、盒装、工具、小家电、配件或套装；选择最能展示功能面的 3/4 白底棚拍视角。保持源图中的真实轮廓、材质、颜色、Logo、接口、按钮和配件数量；让商品主体完整、清晰、居中，占画面约 78%。不要为了美观而重塑产品，也不要添加源图不存在的场景元素。
```

## Prompt Assembly

Combine the source facts, base specification, category add-on, and negative prompt into one ready-to-copy prompt. Keep the prompt actionable and image-model friendly.

Example pattern:

```text
请参考上传的实拍图，将这款<品类>标准化为电商白底商品图。保留<关键事实>。
<Base Specification>
<Category Add-On>
Negative prompt: <Negative Prompt>
```

If details are uncertain, say `源图中不可确认的细节不要生成或自行补全`. Do not ask for clarification about uncertain product details unless the source image is missing or unreadable. The mandatory credit approval still applies before generation.

## Acceptance Checklist

Before presenting a generated image, check:

- **Identity:** product category, silhouette, color, material, component count, ports, buttons, camera modules, handles, straps, and accessories match the source.
- **Brand integrity:** keep a visible logo unchanged when the editing model can preserve it; if reliable preservation is not possible, disclose the limitation instead of inventing or rewriting brand text.
- **Composition:** the complete product is visible, centered, uncropped, and has marketplace-safe margins.
- **Background:** background is neutral white without unwanted props, text, hands, scenery, borders, or watermarks.
- **Lighting:** highlights and contact shadow clarify shape without changing material or hiding edges.
- **No hallucination:** no new feature, certification, packaging, accessory, claim, or decorative element appears.

When a defect affects product identity, treat it as a failed result. When the issue is only a small aesthetic preference, describe it and let the user decide whether another paid generation is worthwhile.

## AI Creative MCP execution

Read [references/aicreative-mcp.md](references/aicreative-mcp.md) before the first generation. This branch uses AI Creative MCP for generation; the calling agent still identifies visible product facts and reviews the result. Python 3.11+ and Pillow are required.

Bind the local source photo to its matching asset ID or accessible source URL. Then save the combined specification and exclusions to a prompt file and run:

```bash
python3 scripts/image_tool.py edit \
  --image /absolute/path/product.png \
  --prompt-file /absolute/path/product.prompt.txt \
  --size 1024x1024 --output outputs/product.png \
  --save-json outputs/product.json
```

Use `--dry-run` for an offline preview. Public visibility defaults to OFF. `--size` controls the ratio hint; actual output dimensions follow the chosen model tier. Do not promise exact platform dimensions or product identity without inspecting the result. Mask-based local editing and transparent-background controls are not exposed by this MCP.
