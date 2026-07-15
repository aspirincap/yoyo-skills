---
name: open-tiktok-script
description: |
  TikTok短视频与TikTok Shop带货脚本创作工作流。从竞品TikTok视频拆解到脚本、分镜、Creator Brief和投放素材生成：TikTok链接/本地视频收集→Gemini视频分析→TikTok-native创意机制提炼→脚本+分镜生成→西方语境安全审校。
  当用户提到"TikTok脚本"、"TikTok Shop"、"Spark Ads"、"TikTok素材"、"UGC脚本"、"海外短视频带货"、"竞品TikTok拆解"、"TikTok视频分析"、"短视频广告脚本"时使用此技能。
---

# TikTok短视频脚本创作

从竞品TikTok拆解到脚本生成的完整工作流。目标不是把抖音话术直译成英文，而是生成更像TikTok创作者自然会拍、观众愿意停留、品牌能放心投放的内容。

## 灵感来源与署名

本 Skill 的六步工作流、竞品视频拆解思路和参考库组织方式，灵感来自花叔（[`alchaincyf`](https://github.com/alchaincyf)）的 [`huashu-douyin-script`](https://github.com/alchaincyf/huashu-skills/tree/master/huashu-douyin-script)。本项目在此基础上针对 TikTok、TikTok Shop、Spark Ads、英文 creator-native 表达和西方语境安全边界进行了独立改写。

本次署名核对基于上游固定提交 [`35e7cf31328f6de07e5d125bfd094791f84b2352`](https://github.com/alchaincyf/huashu-skills/commit/35e7cf31328f6de07e5d125bfd094791f84b2352)（检查日期：2026-07-15）。

上游仓库截至 2026-07-15 未声明许可证。本项目维护者已于 2026-07-15 确认取得公开发布本改编项目的授权；发布时继续保留来源署名。该授权不代表上游仓库其他内容自动获得相同许可证。详见 `README.md` 和 `NOTICE.md`。

## 渠道原则

TikTok脚本优先追求 creator-native：
- 开头1-2秒先抓眼球，3秒内说清“为什么要继续看”。
- 口吻像真实创作者分享，不像广告播报、电视购物或中文电商硬广。
- 卖点表达要具体、可演示、可感知，少用大词和空泛承诺。
- 保留适度夸张和情绪，不按中文广告法的“极限词”清单机械审稿；只有在无法证明、容易误导、医疗/金融/身体焦虑等高风险场景才改写。
- 西方语境的保护群体边界必须严守：不能冒犯、刻板化、排除或利用残疾、种族/族裔、肤色、国籍、宗教、性别、性别认同、性取向、年龄、身材、疾病/健康状态等身份属性。

## 环境要求

- Python 3.10+
- `uv`（Python包管理器）
- `yt-dlp`（TikTok视频下载，需 `pip install yt-dlp` 或 `brew install yt-dlp`）
- Gemini视频分析使用用户配置的 Gemini-compatible endpoint，本 skill 使用独立的项目内配置文件：
  - 默认 Base URL：`https://generativelanguage.googleapis.com`
  - 默认模型：`gemini-2.5-flash`
  - 默认 endpoint：`/v1beta/models/gemini-2.5-flash:generateContent`
  - API Key 优先从 shell 环境读取，其次从本 skill 项目内的 `SKILL_DIR/.env` 读取
  - Key 环境变量按顺序支持：`GEMINI_VIDEO_API_KEY`、`GEMINI_API_KEY`、`GOOGLE_API_KEY`、`NEWAPI_API_KEY`
  - 不读取 `~/.config/gemini-video-analysis/.env`，也不读取 `GEMINI_VIDEO_ENV_FILE`
  - 不把密钥写进 `SKILL.md`；本地持久配置请使用 `SKILL_DIR/.env`
- 可选：用户明确同意后，使用其 Chrome/Edge/Firefox TikTok 会话 Cookie。不得自动读取浏览器 Cookie，也不得绕过私密、年龄或地域访问限制。仅分析用户有权访问和使用的内容，下载视频不得随交付物再分发。

视频分析会把本地视频发送到用户配置的外部 Gemini-compatible provider。第一次上传前说明目标域名并取得用户同意；不要上传含敏感个人信息、未授权人物或机密素材的视频。

**路径约定**：下文中 `SKILL_DIR` 指本 `SKILL.md` 所在目录的绝对路径。运行脚本前，先用 `dirname` 或 Glob 工具确定 `SKILL.md` 的实际位置，替换 `SKILL_DIR`。

## 6步工作流

### Step 1: 收集输入

向用户收集以下信息。

**必填**：
- TikTok视频链接或本地视频文件（1-5个对标/竞品视频；没有也可以直接写脚本）
- 产品信息：名称、核心卖点、目标人群、价格、购买路径
- 目标市场和语言：如 US/UK/CA/AU；英语、西语等
- 脚本类型：Organic TikTok、TikTok Shop、Spark Ads、Paid In-Feed Ad、Creator Brief

**选填**：
- 产品图片或落地页
- 目标时长（Organic/TikTok Shop 默认25-35秒，Paid Ad 默认15-25秒）
- 品牌调性：专业、亲切、搞笑、clean girl、mom creator、fitness creator等
- 创作者人设：年龄段、生活方式、镜头表达习惯
- 投放目标：点击商品卡、进店、关注、评论互动、加购、转化

如果用户只提供了部分信息，先用已有信息推进；只在缺失会影响脚本方向时再追问。

---

### Step 2: 下载或整理视频

如果用户提供TikTok链接，运行下载脚本：

```bash
uv run SKILL_DIR/scripts/download_tiktok.py \
  --urls "URL1" "URL2" \
  --output-dir _temp/tiktok-downloads
```

**参数说明**：
- `--urls`：支持 `tiktok.com/@user/video/...`、`vm.tiktok.com`、`vt.tiktok.com`、分享文本中的链接。
- `--output-dir`：默认当前工作目录下 `_temp/tiktok-downloads/`。
- `--cookies-browser`：默认不启用；如下载失败可指定 `chrome`、`edge` 或 `firefox`。

**下载失败时**：
1. 提示用户确认链接可公开访问，或浏览器已登录TikTok。
2. 如确需浏览器 Cookie，先说明将读取用户自己的浏览器会话并取得明确同意，再使用 `--cookies-browser chrome`。
3. 不尝试绕过私密、年龄或地域限制；建议用户在有权访问的前提下手动提供视频。
4. 建议用户手动下载视频放入 `_temp/tiktok-downloads/`，继续后续分析。

---

### Step 3: Gemini视频分析（可并行）

对每个下载成功的视频，在用户同意后调用 Gemini 视频分析。此脚本只支持本地视频文件，通过用户配置的 Gemini-compatible endpoint 发送 `inlineData` base64；不支持 YouTube URL、远程 URL、`fileData.fileUri` 或 Gemini File API。

```bash
uv run SKILL_DIR/scripts/analyze_video.py \
  --video "_temp/tiktok-downloads/tiktok-1-xxx.mp4" \
  --prompt "PROMPT_BELOW" \
  --model flash \
  --resolution medium \
  --output "_temp/tiktok-downloads/analysis-1.md"
```

**使用 flash 模型 + medium 分辨率**：`--model flash` 默认映射到 `gemini-2.5-flash`，短视频通常足够；实际可用模型和价格由用户的 provider 决定。

**Key 与 Base URL**：
- 默认读取 `GEMINI_VIDEO_API_KEY` / `GEMINI_API_KEY` / `GOOGLE_API_KEY` / `NEWAPI_API_KEY`。
- 默认读取 `GEMINI_VIDEO_BASE_URL`，未设置时使用 Google Gemini API：`https://generativelanguage.googleapis.com`。
- 本地持久 key 使用 `SKILL_DIR/.env`，不复用 `$gemini-video-analysis` 的全局配置文件。
- 默认仅发送 `x-goog-api-key`。兼容网关如需 Bearer，可加 `--auth-mode bearer`；确有需要时才使用 `--auth-mode both`。

**文件大小**：默认 inline payload 安全限制为 20MB。超过时先剪短、压缩或拆分视频，不切换到 File API。

**多个视频可并行分析**。

**TikTok分析Prompt**：

```text
作为资深TikTok创意策略师和跨文化短视频编导，请对这个视频进行8维度深度拆解。
请用中文输出，但保留视频中的英文原句、字幕和口播表达。

## 1. 前2秒钩子分析
- 第一帧：画面主体、构图、字幕、动作、情绪
- 文案钩子：完整转录开头口播/字幕
- 视觉钩子：动作冲击、before/after、POV、反差、文字弹出、产品奇观、情绪表情
- 为什么适合TikTok：是否像真实创作者内容，是否有scroll-stopping信号
- 钩子强度评分（1-10）及理由

## 2. Creator人设与信任来源
- 创作者像谁：普通用户、专家、妈妈、健身人群、美妆达人、学生、办公室人群等
- 信任来自哪里：个人体验、演示证据、专业背景、评论区反馈、社交证明
- 是否有明显广告腔

## 3. 分镜结构
用表格拆解每个镜头：
| 时间 | 景别 | 画面内容 | 口播/字幕 | 转场/剪辑 |

## 4. 节奏与留存
- 每个剪辑点大概间隔
- 是否每3-5秒有信息变化
- BGM、音效、停顿、表情和字幕是否配合
- 是否适合15秒/30秒版本二次剪辑

## 5. TikTok-native表达
- 口语、梗、评论区感、POV、duet/stitch感、真实测评感
- 字幕样式、屏幕文字密度、emoji/符号使用
- 是否像平台内容，而不是品牌广告片

## 6. 转化设计
- CTA出现时机
- TikTok Shop商品卡/橱窗/链接/评论区引导方式
- 价格锚定、赠品、优惠、对比演示
- 从观看到购买的路径是否自然

## 7. 西方语境安全检查
- 是否触碰保护群体：残疾、种族/族裔、肤色、国籍、宗教、性别、性别认同、性取向、年龄、身材、疾病/健康状态
- 是否包含身体羞辱、性别/种族刻板印象、残障歧视、嘲讽口音或文化挪用
- 是否把用户的敏感身份当作问题、缺陷或恐惧来营销
- 如有风险，给出自然、不扫兴的替代表达

## 8. 可复制要素
- 可复制的钩子句式、分镜结构、镜头动作、字幕节奏、CTA
- 不可复制的元素：特定创作者人格、不可验证声明、受版权保护音乐/素材、容易冒犯的文化梗
```

---

### Step 4: TikTok公式提炼 ← 用户确认节点

**有竞品视频时** → 汇总分析结果：

读取所有 `analysis-*.md` 文件，同时读取 `references/proven-formulas.md` 中的TikTok公式作为对照，由Claude汇总提炼：

1. **品类共性**：多个视频共同的停留和转化要素。
2. **钩子公式**：证据中重复出现、值得测试的开头动作、字幕和口播模板。
3. **Creator angle**：适合该产品的创作者人设和信任来源。
4. **推荐分镜结构**：15秒、30秒版本的镜头流程。
5. **转化路径**：TikTok Shop、Spark Ads、Paid Ad或自然种草的CTA策略。
6. **文化安全边界**：需要避免的保护群体、身体焦虑、刻板印象和语气问题。

**无竞品视频时** → 使用创意公式参考库：

读取 `references/proven-formulas.md`，根据产品品类和目标市场选择最接近的公式作为基线。提醒用户：无竞品分析时，脚本可先用于首轮测试，后续最好用真实竞品视频迭代。

**保存汇总**到 `_temp/tiktok-downloads/[产品名]-TikTok分析汇总.md`。

**展示给用户确认**：
- 目标市场和语言是否正确。
- 创作者人设是否符合品牌。
- 脚本类型是否正确。
- 哪些表达需要更保守，哪些可以更大胆。

**公式沉淀**：分析完成后，把新品类公式与来源 URL、观察日期和证据强度保存到当前项目的 `_temp/tiktok-downloads/[产品名]-learned-formula.md`。不要自动修改已安装 Skill 的参考库；经人工审核后再决定是否合并。

---

### Step 5: 脚本+分镜生成

基于TikTok公式 + 产品信息 + 口语风格样本生成脚本。

**生成前准备**：
1. 读取 `references/script-style-samples.md` 获取TikTok口语风格范例。
2. 读取 `references/analysis-dimensions.md` 中的脚本类型区别表。
3. 读取Step 4的分析汇总。

#### Organic / TikTok Shop脚本模板

```text
你是TikTok短视频编导，擅长把产品卖点写成creator-native内容，而不是硬广。

## 任务
为以下产品生成一个{时长}秒的{Organic TikTok/TikTok Shop}脚本。

## 产品信息
{产品名称、核心卖点、目标人群、价格、品牌信息、购买路径}

## 目标市场与语言
{国家/地区、语言、受众文化语境}

## TikTok公式
{Step 4提炼的公式}

## 口语风格要求
- 像真实创作者在手机前说话，短句、直接、有个人感受。
- 前2秒必须有画面动作或反差，不只靠一句口播。
- 卖点最多3个，必须能被镜头证明或演示。
- 允许适度夸张、俏皮、强利益点；不要按中文“极限词”过度审查。
- 涉及功效、健康、身体、金钱结果时，改成体验/可能性/使用场景，不做确定性保证。
- 不使用冒犯保护群体的表达，不用身份羞辱制造痛点。

原创合成风格范例：
{从script-style-samples.md选取同品类或风格接近的1-2个样本}

## 输出要求

### Part A：完整脚本
- 标注每段预估时长。
- 开头2秒包含视觉动作+屏幕文字。
- 中段用演示、对比、场景化表达卖点。
- 结尾CTA自然：shop the link、tap the product card、check the comments、save this等。
- 提供英文脚本；如用户要求中文解释，可附中文创意说明。

### Part B：分镜表格
| 镜号 | 时长 | 景别 | 画面内容 | 口播/字幕 | 拍摄建议 |

### Part C：Creator拍摄提示
- 道具/场景
- 表情和语气
- 字幕风格
- 可剪成15秒版本的删减建议
```

#### Paid In-Feed / Spark Ads脚本模板

```text
你是TikTok performance creative strategist，擅长写可投放、可测试、但仍然像TikTok内容的广告脚本。

## 任务
为以下产品写一条{时长}秒TikTok Paid In-Feed/Spark Ads脚本。

## 产品信息
{产品名称、核心卖点、目标人群、价格、投放目标}

## TikTok公式
{Step 4提炼的公式}

## Paid素材特殊要求
- 前2秒必须有强视觉钩子，不要只用问句开头。
- 信息密度高，但语气仍像创作者，不像品牌播音。
- 每条素材只测试一个主卖点或一个主痛点。
- CTA清晰：tap to shop、get yours、try it today、see the demo等。
- 不承诺确定性结果，不做无法证明的医疗、金融、外貌改变承诺。
- 不用保护群体、身体羞辱或身份焦虑做转化杠杆。

## 输出
### Part A：完整脚本（标注时长）
### Part B：分镜表格
| 镜号 | 时长 | 画面内容 | 口播/字幕 | 素材建议 |
### Part C：A/B测试变体
- Hook A/B/C
- CTA A/B
- 15秒剪辑版
```

#### Creator Brief模板

```text
请把脚本转成TikTok creator brief，方便达人拍摄。

输出：
1. Creative angle（一句话）
2. Must-show shots（必须拍到的镜头）
3. Talking points（必须说到，但不要逐字背）
4. Do not say（禁说/高风险表达）
5. CTA
6. Examples of natural phrasing（3句）
```

---

### Step 6: TikTok审校 ← 用户确认节点

对生成的脚本进行5项检查。审校目标是“像TikTok、能投放、不冒犯”，不是把脚本磨成没有能量的安全稿。

#### 检查1：TikTok-native程度
- 是否像真实创作者会说的话。
- 是否前2秒有动作、反差、字幕或表情。
- 是否避免品牌宣传片、说明书、电视购物腔。
- 英文是否自然，避免中式直译。

#### 检查2：钩子强度
- 第一帧是否能让人停一下。
- 口播和画面是否同步强化一个点。
- 是否适合目标人群的语气和内容习惯。

#### 检查3：节奏与时长
- 每段时长是否合理。
- 总时长是否在目标范围内。
- 是否每3-5秒有画面或信息变化。
- 是否可以自然剪出15秒版本。

#### 检查4：真实性与投放风险

不要机械套用中文广审“极限词”思维。TikTok素材可以保留强表达，但以下内容要改：

**4a. 无法证明的绝对承诺**：
- 高风险：guaranteed、cures、permanent、works for everyone、lose X pounds in Y days。
- 可改：helped me、designed to support、made it easier for me、I noticed、for my routine。

**4b. 健康/身体/金融/安全结果**：
- 不承诺疾病治疗、体重变化、皮肤永久改善、收益结果、人身安全结果。
- 用体验、演示和场景表达，不把结果说成必然。

**4c. 虚假稀缺和误导对比**：
- 避免 fake countdown、fake sold out、unverifiable “#1”、贬低竞品。
- 可以用真实优惠、真实库存、真实用户评价或演示对比。

**4d. 版权和平台感**：
- 不建议依赖未授权音乐、影视片段、名人肖像。
- 不伪装成评论区、新闻、医生/专家背书，除非确有授权和证明。

#### 检查5：西方语境保护群体安全

这些边界比“极限词”更重要。凡是触碰以下情况，必须重写：

- **残疾/健康状态**：不用 lame、crazy、insane、psycho、OCD 等词当梗；不把残障、疾病或神经差异当成笑点、缺陷或恐惧。
- **种族/族裔/肤色/国籍/宗教**：不模仿口音嘲讽，不用刻板印象，不暗示某群体天生如何。
- **性别/性取向/性别认同**：不贬低女性/男性/跨性别/非二元/同性恋群体，不用羞辱式“男人/女人都怎样”做钩子。
- **年龄/身材/外貌**：避免 body shaming、age shaming；可以描述用户困扰，但不能把人群身份说成问题本身。
- **敏感身份定向**：不要写“Are you disabled/overweight/depressed?”这类直接点名用户敏感属性的广告钩子。改成场景或需求：“Need a grip that's easier to hold?”、“Looking for a gentler daily routine?”

**改写原则**：保留冲击力，替换攻击对象。把“羞辱某类人”改成“指出具体场景里的麻烦”；把“身份焦虑”改成“使用体验改善”。

#### 审校输出

展示给用户：
1. 原句
2. 风险类型
3. 改写句
4. 为什么这样改

用户确认后，再应用修改。

---

## 文件保存规则

所有中间产物和最终输出保存在 `_temp/tiktok-downloads/`：

```text
_temp/tiktok-downloads/
├── tiktok-1-[ID].mp4
├── tiktok-2-[ID].mp4
├── analysis-1.md
├── analysis-2.md
├── [产品名]-TikTok分析汇总.md
├── [产品名]-Organic脚本.md
├── [产品名]-TikTokShop脚本.md
├── [产品名]-PaidAd脚本.md
└── [产品名]-CreatorBrief.md
```

## 参考资源

| 资源 | 路径 | 用途 |
|------|------|------|
| 分析维度框架 | `references/analysis-dimensions.md` | TikTok 8维度分析+脚本类型区别 |
| 创意公式参考 | `references/proven-formulas.md` | 待真实证据验证的品类创意假设 |
| 原创合成样本 | `references/script-style-samples.md` | 非平台逐字稿的 few-shot 风格范例 |
| 视频下载脚本 | `scripts/download_tiktok.py` | TikTok视频下载（yt-dlp） |
| Gemini视频分析 | `scripts/analyze_video.py` | 使用用户配置的 Gemini-compatible endpoint 对本地视频做理解和拆解 |

## 快速使用

**有竞品视频时**：
1. 收集TikTok链接和产品信息。
2. 下载并分析视频。
3. 展示分析汇总，确认创意方向。
4. 生成脚本、分镜和Creator Brief。
5. 做TikTok-native和西方语境安全审校。
6. 将新品类公式与来源保存到项目输出，人工审核后再合并参考库。

**无竞品视频时**：
1. 收集产品信息、目标市场、脚本类型。
2. 从 `references/proven-formulas.md` 选取品类公式。
3. 生成脚本、分镜和Creator Brief。
4. 审校后交付。

总耗时：有视频约15-20分钟，无视频约5-10分钟。
