<div align="center">

**中文** · [English](./README.en.md)

# 🧰 Yoyo Skills

#### 跨境电商广告投放 & 选品常用 AI 技能集，都开源在这里

[![License](https://img.shields.io/badge/License-MIT-3B82F6?style=for-the-badge)](./LICENSE)
[![Skills](https://img.shields.io/badge/Skills-9-10B981?style=for-the-badge)](#-skills)
[![AgentSkills](https://img.shields.io/badge/AgentSkills-Standard-8B5CF6?style=for-the-badge)](https://agentskills.io)

![Claude Code](https://img.shields.io/badge/Claude_Code-Skill-D97706?style=flat-square&logo=anthropic&logoColor=white)
![Codex](https://img.shields.io/badge/Codex-Skill-10B981?style=flat-square&logo=openai&logoColor=white)

</div>

覆盖跨境电商从 **商品选品 → 竞品素材分析 → 社交趋势研究 → TikTok 脚本 → 商品图标准化 → 商品详情页 → 广告策略 → 故事板 → UGC 视频** 的完整链路。

- **Skills** — Agent 能直接加载的结构化指令集，遵循 [Agent Skills](https://agentskills.io) 开放标准。Claude Code、Codex 都能装

---

## 📋 目录

### Skills

| 名字 | 一句话 |
|---|---|
| 🛒 [**yiwugo-product-sourcing（义乌购选品）**](#-yiwugo-product-sourcing义乌购选品) | API-first 义乌购选品，不打开浏览器就能完成从关键词搜索到货源短名单的全流程 |
| 🔍 [**product-creative-scraper（产品素材抓取分析）**](#-product-creative-scraper产品素材抓取分析) | 从产品链接批量抓取商品图和卖点，输出飞书多维表格 |
| 📈 [**trend-to-creative-brief（趋势转广告创意）**](#-trend-to-creative-brief趋势转广告创意) | 直接检索近期公共 TikTok/Instagram 帖子，把有日期、有来源的趋势证据转成原创广告测试方案 |
| 🎙️ [**open-tiktok-script（海外 TikTok 脚本）**](#-open-tiktok-script海外-tiktok-脚本) | 从公共竞品视频拆解到 creator-native 脚本、分镜、Creator Brief 和广告安全审校 |
| 📦 [**standard-product-image（标准商品图）**](#-standard-product-image标准商品图) | 把实拍产品图整理成结构真实、平台友好的电商白底商品图或提示词 |
| 🧩 [**product-detail-page-pipeline（商品详情页流水线）**](#-product-detail-page-pipeline商品详情页流水线) | 从商品证据和买家顾虑规划多屏详情页，经逐页确认后独立生图并本地拼成长图 |
| 🎯 [**ad-campaign-workflow（广告投放工作流）**](#-ad-campaign-workflow广告投放工作流) | 从产品 URL 到 Meta/TikTok 完整投放策略包：受众、素材、文案、出价一把出 |
| 🎬 [**script-to-storyboard-video（脚本转故事板视频）**](#-script-to-storyboard-video脚本转故事板视频) | 已有广告脚本时先生成故事板并人工确认，再生成竖版广告视频 |
| 📱 [**product-to-ugc-video（产品转 UGC 视频）**](#-product-to-ugc-video产品转-ugc-视频) | 从产品图规划稳定创作者、连续关键帧和可恢复的 UGC 视频片段 |

---

## 📦 安装方式

在 Claude Code、Codex 等支持 Skill 的 Agent 里，直接说：

```
帮我安装这个 skill：https://github.com/aspirincap/yoyo-skills/tree/main/<skill-name>
```

把 `<skill-name>` 换成上表中的目录名。Agent 会自己 clone 到对应目录。

或者手动 clone：

```bash
# Claude Code
git clone https://github.com/aspirincap/yoyo-skills.git ~/.claude/skills/

# Codex
git clone https://github.com/aspirincap/yoyo-skills.git ~/.codex/skills/
```

---

## 🔌 AI 网关：只配置一次

五个 AI 调用型 Skill 支持任意 NewAPI-compatible 网关，并共享供应商中立的 `AI_GATEWAY_*` 配置：

```bash
python3 shared/ai-gateway/configure_ai_gateway.py
```

配置安全写入 `~/.config/ai-gateway/config.env`，供 `product-creative-scraper`、`open-tiktok-script`、`script-to-storyboard-video`、`product-to-ugc-video` 和 `product-detail-page-pipeline` 共用。详情见 [AI_GATEWAY.md](./AI_GATEWAY.md)。

---

## ✨ Skills

<a id="-skills"></a>

<table>
<tr><td>

### 🛒 yiwugo-product-sourcing（义乌购选品）

> *"在义乌购翻几百页找货源太痛苦了——让 AI 自动搜、自动筛、自动出报告。"*

一个 API-first 的义乌购选品 Skill，**不需要打开浏览器**就能完成从关键词搜索 → AI 推荐 → 产品卡片拉取 → 交叉筛选 → Excel/HTML 报告输出的完整选品流程。

**核心能力**

- **AI 语义搜索**：中文自然语言描述选品需求，义乌购 AI 自动匹配产品
- **产品卡片批量拉取**：无需登录，自动提取产品 ID 并通过 API 获取价格/MOQ/店铺信息
- **自动评分排序**：综合价格、MOQ、风险标记给出 Priority A/B/C/Avoid 分级
- **跨境外贸风险筛查**：自动标记带电、食品接触、儿童用品、品牌侵权等合规风险
- **三格式报告输出**：终端 Markdown 预览 + Excel（含预览图）+ HTML（含产品主图）

**怎么触发**

```
帮我找义乌购上的古风发簪货源，采购价要低
用义乌购选品：半导体散热风扇，适合跨境电商
帮我看看汉服发饰在义乌购上有什么供应商
```

**使用示例**

```bash
# 单关键词搜索
python3 scripts/yiwugo_ai_api.py --keyword '古风发簪' --constraints '采购价低' --max-products 10 --no-answer

# 多关键词并行搜索
python3 scripts/yiwugo_ai_api.py --keyword '半导体风扇' --keyword '制冷小风扇' --keyword '手持风扇' --sort score --max-products 15

# JSON 输出
python3 scripts/yiwugo_ai_api.py --keyword '汉服发饰' --constraints '低MOQ、不带电' --json
```

**依赖**

```bash
pip install openpyxl Pillow requests
```

**适用平台**：Amazon · TikTok Shop · Shopify · eBay · Shopee/Lazada · Temu

**🌐 跨平台**：Claude Code · Codex

→ [SKILL.md](./yiwugo-product-sourcing/SKILL.md) · [README](./yiwugo-product-sourcing/README.md)

</td></tr>
</table>

<table>
<tr><td>

### 📈 trend-to-creative-brief（趋势转广告创意）

> *"看到平台热点不等于知道品牌该不该跟——先验证证据，再把机制改成可测试的原创广告。"*

直接检索指定日期与市场范围内的公共 TikTok/Instagram 帖子，保留查询、来源日期、互动量、地域置信度和计费信息，再按新鲜度、品牌适配和风险筛选趋势，输出创意角度与测试矩阵。

**核心能力**

- **直接公共数据检索**：动态发现并调用 TikTok/Instagram 搜索操作
- **证据可审计**：保留帖子 URL、发布日期、互动量、query、operation path 与 credits charged
- **市场置信度**：TikTok 按 `region` 过滤；Instagram 缺少国家字段时明确标记未验证
- **原创创意改编**：保留趋势机制，不复制创作者原话、音乐、角色或画面
- **测试与过期管理**：输出学习问题、指标、风险、复查日期和趋势到期时间

**强依赖**

实时检索必须连接 [UnifAPI MCP](https://unifapi.com/zh/mcp)，Server 为 `https://mcp.unifapi.com`。官方使用 OAuth、只读、无需向 Skill 粘贴 API Key，并按返回记录计费。未连接时只能处理用户已经提供的证据。

**怎么触发**

```text
研究最近 14 天美国 TikTok 和 Instagram 上的夜跑装备趋势，转成广告创意 brief
查过去 7 天 TikTok 的 summer running essentials，所有结论注明来源和日期
我已经有三个 Reels 链接，帮我判断 pursue、adapt、watch 还是 skip
```

**🌐 跨平台**：Claude Code · Codex（需支持 MCP）

→ [SKILL.md](./trend-to-creative-brief/SKILL.md) · [README](./trend-to-creative-brief/README.md) · [UnifAPI MCP 安装](https://unifapi.com/zh/mcp)

</td></tr>
</table>

<table>
<tr><td>

### 🎙️ open-tiktok-script（海外 TikTok 脚本）

> *"不是把中文带货话术翻成英文——而是从公开竞品证据中提炼机制，写成创作者真的会说、品牌可以投放的 TikTok 内容。"*

收集最多 5 个公共 TikTok 对标视频，用可配置的 Gemini-compatible 服务拆解钩子、节奏、演示和转化机制，再生成原创的 Organic、TikTok Shop、Spark Ads、Paid In-Feed 脚本、分镜与 Creator Brief。

**核心能力**

- **竞品视频拆解**：下载公开 TikTok 视频，分析钩子、分镜、节奏、卖点与 CTA
- **Creator-native 写作**：生成自然英文口语，避免电视购物式硬广和中文话术直译
- **多种投放格式**：支持 Organic、TikTok Shop、Spark Ads、Paid In-Feed 与 Creator Brief
- **安全审校**：检查广告声明、版权、身体焦虑、保护群体与文化语境风险
- **可配置视频分析**：默认 Google Gemini，也可使用 HTTP/HTTPS Gemini-compatible 网关

**灵感与署名**

六步工作流和参考库组织灵感来自花叔（[`alchaincyf`](https://github.com/alchaincyf)）的 [`huashu-douyin-script`](https://github.com/alchaincyf/huashu-skills/tree/master/huashu-douyin-script)，本项目已确认获得公开发布授权并保留署名。

**怎么触发**

```text
拆解这三个 TikTok 竞品视频，给我的跑步腰包写一条 TikTok Shop 脚本
根据产品卖点写 30 秒 creator-native UGC 脚本和逐镜分镜
把这个 Organic TikTok 改成可投放的 Spark Ads Creator Brief
```

**🌐 跨平台**：Claude Code · Codex

→ [SKILL.md](./open-tiktok-script/SKILL.md) · [README](./open-tiktok-script/README.md) · [NOTICE](./open-tiktok-script/NOTICE.md)

</td></tr>
</table>

<table>
<tr><td>

### 📦 standard-product-image（标准商品图）

> *"供应商实拍图背景乱、角度杂——先保真，再统一成可上架的白底商品图。"*

识别手机、风扇、锅具、餐具、智能手表、筋膜枪等产品类型，提取源图可见事实，生成平台尺寸友好的白底商品图提示词；有生图工具时也能直接执行并按验收清单检查结构漂移。

**核心能力**

- 品类识别与通用品类回退
- 保留颜色、材质、Logo、按钮、接口和配件数量
- 支持用户指定平台尺寸；未指定时使用灵活的安全边距
- 自动生成负面提示词，禁止虚构功能、认证、包装和装饰
- 按商品身份、构图、背景、光影和幻觉逐项验收

**怎么触发**

```text
把这张手持风扇实拍图整理成电商白底商品图
只输出 1600x1600 的商品图提示词，不要生图
这个产品不在预设分类里，用通用规则处理
```

**🌐 跨平台**：Claude Code · Codex

→ [SKILL.md](./standard-product-image/SKILL.md)

</td></tr>
</table>

<table>
<tr><td>

### 🧩 product-detail-page-pipeline（商品详情页流水线）

> *"先让每一屏回答一个购买问题，确认完整方案后再逐屏生图。"*

从商品事实、买家顾虑和平台要求规划 Amazon A+、Shopify、TikTok Shop、淘宝/天猫等多屏详情页。技能强制展示逐页评审包，并把明确批准绑定到 Prompt Pack 哈希；每屏独立调用图片模型，最后只在本地生成 contact sheet 和长图衍生物。

**核心能力**

- 区分可见事实、用户提供事实和无证据声明
- 6–10 屏买家问题驱动的内容结构与共享视觉 DNA
- 逐页文案、证据、禁用声明、画布和引用的强制人工确认
- 缺失引用、过期审批、重复页面和未产图结果默认阻断
- 保留每张原始屏图，仅对装配衍生物做安全裁切和纵向拼接

**怎么触发**

```text
给这款行车记录仪做美国站 6 屏详情页，先逐页给我确认
把这套 Amazon A+ 方案改成淘宝详情长图，但每屏必须独立生成
我已有 prompt_pack.json，先离线 dry-run，不要调用生图 API
```

**依赖**

```bash
pip install -r requirements.txt
python3 scripts/configure_ai_gateway.py
```

**🌐 跨平台**：Claude Code · Codex

→ [SKILL.md](./product-detail-page-pipeline/SKILL.md)

</td></tr>
</table>

<table>
<tr><td>

### 🔍 product-creative-scraper（产品素材抓取分析）

> *"竞品的主图、卖点、风格，批量扒下来放到飞书表格里慢慢看。"*

轻量级产品创意素材抓取和分析工具。从 Shopify/独立站产品页批量提取商品名、价格、图片，再用 AI 分析每张图片的卖点、风格、布局、场景，最终输出飞书多维表格或 CSV。

**核心能力**

- **多源抓取**：支持 App Store、Google Play、Shopify 独立站、通用电商产品页
- **批量处理**：单 URL 或多 URL 列表（CSV/TXT）输入
- **AI 素材分析**：OCR 提取图片文字 + VLM 分析卖点/风格/布局/场景
- **飞书多维表格输出**：商品表 + 图片表，可直接在飞书中协作筛选
- **轻量设计**：无需数据库、向量搜索或 Cloudflare 基础设施

**怎么触发**

```
帮我把这几个产品链接抓一下素材：https://...
帮我把竞品的产品图和卖点扒到飞书表格里
```

**使用示例**

```bash
# 单 URL
python3 scripts/run_product_scrape.py "https://apps.apple.com/app/xxx"

# 多 URL
python3 scripts/run_product_scrape.py --url-file urls.txt --format json

# AI 分析素材图片
python3 scripts/analyze_assets.py --scrape-json scrape.json --format json

# 初始化飞书多维表格
python3 scripts/init_lark_base.py --create --name "Product Creative Scraper MVP"

# 同步到飞书
python3 scripts/sync_lark_base.py --scrape-json scrape.json --analysis-json analysis.json --project "竞品分析"
```

**依赖**

```bash
pip install requests Pillow openpyxl
# AI 分析需要
python3 scripts/configure_ai_gateway.py
```

**🌐 跨平台**：Claude Code · Codex

→ [SKILL.md](./product-creative-scraper/SKILL.md)

</td></tr>
</table>

<table>
<tr><td>

### 🎬 script-to-storyboard-video（脚本转故事板视频）

> *"视频生成成本高，先把脚本和产品图变成故事板，确认没问题再生成。"*

面向“已经有广告脚本”的两阶段视频工作流：先按脚本和产品图生成故事板，停下来等待人工确认，再通过用户配置的 NewAPI-compatible 图片与视频接口生成 9:16 片段。需要创作者人设和连续关键帧时应选择 `product-to-ugc-video`。

> 原 `ad-storyboard-seedance` 已更名；已有安装请改用目录和 Skill 名 `script-to-storyboard-video`。

**核心能力**

- 自动按最长 15 秒拆分广告脚本和故事板
- 产品结构、标签、颜色和广告声明约束
- 强制人工确认门，避免误花视频额度
- 支持 dry-run、并发片段生成、失败日志和项目恢复
- 使用 ffprobe 验证比例、时长、帧率和音频流

**配置**

```bash
python3 scripts/configure_ai_gateway.py
```

**🌐 跨平台**：Claude Code · Codex

→ [SKILL.md](./script-to-storyboard-video/SKILL.md)

</td></tr>
</table>

<table>
<tr><td>

### 📱 product-to-ugc-video（产品转 UGC 视频）

> *"从一张产品图开始，建立稳定创作者，再用连续关键帧生成可拼接的 UGC 视频。"*

把产品图和说明转换成角色一致的短视频项目：规划创作者人设、生成角色参考图、连续关键帧和相邻帧视频片段，并保存完整 manifest、prompt、日志和合并信息。

**核心能力**

- 中性、可配置的创作者设定，不默认性别或年龄
- 角色、服装、产品和场景连续性约束
- Planner、图片与视频 Provider 分开配置
- `--heuristic-plan --dry-run` 可离线预览整个项目
- 保留成功片段和中间产物，便于恢复失败任务

**离线预览**

```bash
python3 scripts/product_to_ugc.py \
  --product-image /path/to/product.jpg \
  --description "产品可见特点与真实使用场景" \
  --heuristic-plan --dry-run
```

**🌐 跨平台**：Claude Code · Codex

→ [SKILL.md](./product-to-ugc-video/SKILL.md)

</td></tr>
</table>

<table>
<tr><td>

### 🎯 ad-campaign-workflow（广告投放工作流）

> *"拿到一个产品链接，不知道投 Meta 还是 TikTok、受众怎么选、素材怎么做——让这个 Skill 给你出一套完整的投放策略包。"*

跨Meta/TikTok 广告投放工作流。输入一个产品 URL 或产品简介，自动产出：投放策略、受众定位（通用字段 + motata CLI 可消费字段）、广告结构、文案、图片 prompt、验证报告。**不实际创建广告，不花预算**——这是一个分析和准备工具。

**核心能力**

- **产品分析**：自动提取卖点、受众假设、使用场景、风险标记
- **双平台受众定位**：Meta 和 TikTok 的通用受众字段 + motata 平台专用字段
- **Campaign 结构生成**：Meta campaign/adset/ad 和 TikTok campaign/adgroup/ad 完整层级
- **素材策略**：每个 ad 配创意角度、文案、CTA、落地页、图片 prompt
- **验证报告**：预算、受众、素材对齐自动检查

**怎么触发**

```
帮我分析这个产品，出 Meta 和 TikTok 的投放方案：https://...
给这个产品做一套广告投放策略
帮我规划一下这个品的 Meta 受众定位
```

**工作流程**

1. **分析产品** — 读产品链接/简介，提取类目、卖点、受众假设
2. **解析受众字段** — 通过 motata 查询 Meta/TikTok 真实定位数据（依赖motata skill）
3. **推荐投放方案** — 国家、平台预算分配、素材测试结构（需用户确认）
4. **生成 Campaign 结构** — 完整的 campaign/adset/ad 或 campaign/adgroup/ad
5. **验证输出** — 检查预算对齐、受众覆盖、素材数量一致性

**最终产出章节**

- `strategy_brief` — 产品、受众、渠道、国家、预算策略
- `targeting_fields_generic` — 通用受众字段库
- `targeting_fields_motata` — motata 可消费字段库
- `campaign_structure` — Meta/TikTok campaign 层级
- `creative_matrix` — 创意角度、文案、CTA、受众映射
- `image_prompt_pack` — 每条广告一个图片 prompt
- `validation_report` — 验证检查、未解析字段、风险警告

**安全规则**

- 只读 motata，不创建广告、不消耗预算
- 所有未解析的平台 ID 明确标记，不伪造
- Campaign/Adset/Ad 默认状态为 draft 或 paused

**🌐 跨平台**：Claude Code · Codex

→ [SKILL.md](./ad-campaign-workflow/SKILL.md)

</td></tr>
</table>

---

## 🔗 选品→创意→投放完整链路

这九个 Skill 可以串联使用，覆盖跨境电商从选品到创意生产的完整流程：

```
yiwugo-product-sourcing     →  找到货源，拿到价格/MOQ/供应商
        ↓
product-creative-scraper    →  分析竞品素材，提取卖点和风格
        ↓
standard-product-image      →  将实拍素材标准化为电商商品图
        ↓
product-detail-page-pipeline →  规划、确认并生成多屏商品详情页
        ↓
ad-campaign-workflow        →  输出 Meta/TikTok 完整投放策略包
        ↓
script-to-storyboard-video  →  已有脚本时生成并确认广告故事板
        ↓
product-to-ugc-video        →  需要创作者连续性时生成 UGC 视频项目
```

---

## 🌟 关于

跨境电商广告投放和选品过程中积累的实用 Skill 集合。如果对你有帮助，给个 ⭐ 就行。有问题或建议，欢迎在 Issues 里提。

---

<div align="center">

[MIT License](./LICENSE) · 自由使用 / 修改 / 再分发

</div>
