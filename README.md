<div align="center">

**中文** · [English](./README.en.md)

# 🧰 Yoyo Skills

#### 跨境电商广告投放 & 选品常用 AI 技能集，都开源在这里

[![License](https://img.shields.io/badge/License-MIT-3B82F6?style=for-the-badge)](./LICENSE)
[![Skills](https://img.shields.io/badge/Skills-3-10B981?style=for-the-badge)](#-skills)
[![AgentSkills](https://img.shields.io/badge/AgentSkills-Standard-8B5CF6?style=for-the-badge)](https://agentskills.io)

![Claude Code](https://img.shields.io/badge/Claude_Code-Skill-D97706?style=flat-square&logo=anthropic&logoColor=white)
![Codex](https://img.shields.io/badge/Codex-Skill-10B981?style=flat-square&logo=openai&logoColor=white)

</div>

这几个 Skill 都是在自己日常投流和选品项目里跑通了一段时间，确实省事，才拿出来开源的。覆盖跨境电商从 **商品选品 → 竞品素材分析 → 广告投放策略** 的完整链路。

- **Skills** — Agent 能直接加载的结构化指令集，遵循 [Agent Skills](https://agentskills.io) 开放标准。Claude Code、Codex 都能装

---

## 📋 目录

### Skills

| 名字 | 一句话 |
|---|---|
| 🛒 [**yiwugo-product-sourcing（义乌购选品）**](#-yiwugo-product-sourcing义乌购选品) | API-first 义乌购选品，不打开浏览器就能完成从关键词搜索到货源短名单的全流程 |
| 🔍 [**product-creative-scraper（产品素材抓取分析）**](#-product-creative-scraper产品素材抓取分析) | 从产品链接/App Store/Google Play 批量抓取商品图和卖点，输出飞书多维表格 |
| 🎯 [**ad-campaign-workflow（广告投放工作流）**](#-ad-campaign-workflow广告投放工作流) | 从产品 URL 到 Meta/TikTok 完整投放策略包：受众、素材、文案、出价一把出 |

---

## 📦 安装方式

在 Claude Code、Codex 等支持 Skill 的 Agent 里，直接说：

```
帮我安装这个 skill：https://github.com/aspirincap/yoyo-skills/tree/main/<skill-name>
```

把 `<skill-name>` 换成你想装的那个，比如 `yiwugo-product-sourcing`、`product-creative-scraper`、`ad-campaign-workflow`。Agent 会自己 clone 到对应目录。

或者手动 clone：

```bash
# Claude Code
git clone https://github.com/aspirincap/yoyo-skills.git ~/.claude/skills/

# Codex
git clone https://github.com/aspirincap/yoyo-skills.git ~/.codex/skills/
```

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

### 🔍 product-creative-scraper（产品素材抓取分析）

> *"竞品的主图、卖点、风格，批量扒下来放到飞书表格里慢慢看。"*

轻量级产品创意素材抓取和分析工具。从 App Store、Google Play、Shopify/独立站产品页批量提取商品名、价格、图片，再用 AI 分析每张图片的卖点、风格、布局、场景，最终输出飞书多维表格或 CSV。

**核心能力**

- **多源抓取**：支持 App Store、Google Play、Shopify 独立站、通用电商产品页
- **批量处理**：单 URL 或多 URL 列表（CSV/TXT）输入
- **AI 素材分析**：OCR 提取图片文字 + VLM 分析卖点/风格/布局/场景
- **飞书多维表格输出**：商品表 + 图片表，可直接在飞书中协作筛选
- **轻量设计**：无需数据库、向量搜索或 Cloudflare 基础设施

**怎么触发**

```
帮我把这几个产品链接抓一下素材：https://...
分析一下这个 App Store 应用的截图卖点
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
export GEMINI_API_KEY="your-key"
```

**🌐 跨平台**：Claude Code · Codex

→ [SKILL.md](./product-creative-scraper/SKILL.md)

</td></tr>
</table>

<table>
<tr><td>

### 🎯 ad-campaign-workflow（广告投放工作流）

> *"拿到一个产品链接，不知道投 Meta 还是 TikTok、受众怎么选、素材怎么做——让这个 Skill 给你出一套完整的投放策略包。"*

平台无关的 Meta/TikTok 广告投放工作流。输入一个产品 URL 或产品简介，自动产出：投放策略、受众定位（通用字段 + motata CLI 可消费字段）、广告结构、文案、图片 prompt、验证报告。**不实际创建广告，不花预算**——这是一个分析和准备工具。

**核心能力**

- **产品分析**：自动提取卖点、受众假设、使用场景、风险标记
- **双平台受众定位**：Meta 和 TikTok 的通用受众字段 + motata 平台专用字段
- **Campaign 结构生成**：Meta campaign/adset/ad 和 TikTok campaign/adgroup/ad 完整层级
- **素材策略**：每个 ad 配创意角度、文案、CTA、落地页、图片 prompt
- **验证报告**：预算、受众、素材对齐自动检查
- **Google 除外**：默认只覆盖 Meta + TikTok

**怎么触发**

```
帮我分析这个产品，出 Meta 和 TikTok 的投放方案：https://...
给这个产品做一套广告投放策略
帮我规划一下这个品的 Meta 受众定位
```

**工作流程**

1. **分析产品** — 读产品链接/简介，提取类目、卖点、受众假设
2. **解析受众字段** — 通过 motata 查询 Meta/TikTok 真实定位数据（需要 token）
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

## 🔗 选品→投放完整链路

这三个 Skill 可以串联使用，覆盖跨境电商从选品到投放的全流程：

```
yiwugo-product-sourcing     →  找到货源，拿到价格/MOQ/供应商
        ↓
product-creative-scraper    →  分析竞品素材，提取卖点和风格
        ↓
ad-campaign-workflow        →  输出 Meta/TikTok 完整投放策略包
```

---

## 🌟 关于

跨境电商广告投放和选品过程中积累的实用 Skill 集合。如果对你有帮助，给个 ⭐ 就行。有问题或建议，欢迎在 Issues 里提。

---

<div align="center">

[MIT License](./LICENSE) · 自由使用 / 修改 / 再分发

</div>