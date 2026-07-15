<div align="center">

[中文](./README.md) · **English**

# 🧰 Yoyo Skills

#### AI skills for cross-border ecommerce ads & sourcing — all open-sourced here

[![License](https://img.shields.io/badge/License-MIT-3B82F6?style=for-the-badge)](./LICENSE)
[![Skills](https://img.shields.io/badge/Skills-8-10B981?style=for-the-badge)](#-skills)
[![AgentSkills](https://img.shields.io/badge/AgentSkills-Standard-8B5CF6?style=for-the-badge)](https://agentskills.io)

![Claude Code](https://img.shields.io/badge/Claude_Code-Skill-D97706?style=flat-square&logo=anthropic&logoColor=white)
![Codex](https://img.shields.io/badge/Codex-Skill-10B981?style=flat-square&logo=openai&logoColor=white)

</div>

Each skill is designed around practical ecommerce work. Together they cover: **product sourcing → competitor analysis → social trend research → TikTok scripting → product image standardization → ad strategy → storyboards → UGC video**.

- **Skills** — Structured instruction sets that agents load directly. Follows the [Agent Skills](https://agentskills.io) open standard. Works with Claude Code and Codex

---

## 📋 Index

### Skills

| Name | One-liner |
|---|---|
| 🛒 [**yiwugo-product-sourcing**](#-yiwugo-product-sourcing) | API-first Yiwugo sourcing — search keywords, get product cards with prices/MOQ, and export Excel/HTML reports, no browser needed |
| 🔍 [**product-creative-scraper**](#-product-creative-scraper) | Batch scrape product images and selling points from URLs, App Store, Google Play, Shopify stores, then analyze with AI and sync to Feishu Base |
| 📈 [**trend-to-creative-brief**](#-trend-to-creative-brief) | Directly research dated public TikTok/Instagram evidence and turn reusable mechanics into original ad tests |
| 🎙️ [**open-tiktok-script**](#-open-tiktok-script) | Turn public competitor videos into creator-native scripts, storyboards, Creator Briefs, and advertising-safety reviews |
| 📦 [**standard-product-image**](#-standard-product-image) | Turn real product photos into faithful, marketplace-ready white-background images or editing prompts |
| 🎯 [**ad-campaign-workflow**](#-ad-campaign-workflow) | Turn a product URL into a complete Meta/TikTok ad strategy package — audiences, creatives, copy, and validation reports |
| 🎬 [**script-to-storyboard-video**](#-script-to-storyboard-video) | When an ad script already exists, generate storyboards, require approval, then create vertical ad clips |
| 📱 [**product-to-ugc-video**](#-product-to-ugc-video) | Build a consistent creator, adjacent keyframes, recoverable segments, and merge metadata from a product image |

---

## 📦 Install

In any agent that supports Skills (Claude Code, Codex), just say:

```
Install this skill: https://github.com/aspirincap/yoyo-skills/tree/main/<skill-name>
```

Replace `<skill-name>` with any directory name in the table above. The agent will clone it into the right directory for you.

Or clone manually:

```bash
# Claude Code
git clone https://github.com/aspirincap/yoyo-skills.git ~/.claude/skills/

# Codex
git clone https://github.com/aspirincap/yoyo-skills.git ~/.codex/skills/
```

---

## 🔌 Configure one AI gateway

Four AI-calling skills support any NewAPI-compatible gateway through shared, provider-neutral `AI_GATEWAY_*` configuration:

```bash
python3 shared/ai-gateway/configure_ai_gateway.py
```

The command securely writes `~/.config/ai-gateway/config.env` for `product-creative-scraper`, `open-tiktok-script`, `script-to-storyboard-video`, and `product-to-ugc-video`. See [AI_GATEWAY.md](./AI_GATEWAY.md).

---

## ✨ Skills

<a id="-skills"></a>

<table>
<tr><td>

### 🛒 yiwugo-product-sourcing

> *"Scrolling through hundreds of Yiwugo pages to find suppliers is painful — let AI search, filter, and report for you."*

API-first Yiwugo (Yiwu wholesale market) product sourcing skill. The full pipeline — keyword search → AI recommendations → product card fetching → scoring & risk screening → Excel/HTML reports — runs **without opening a browser**.

**Key capabilities**

- **AI semantic search**: Natural language sourcing queries in Chinese, auto-matched by Yiwugo AI
- **Batch product card fetching**: No login required — extracts product IDs and fetches price/MOQ/shop info via API
- **Auto scoring & ranking**: Priority A/B/C/Avoid with composite score from price, MOQ, and risk flags
- **Cross-border risk screening**: Auto-flags battery, food-contact, children's products, and brand/IP risks
- **Triple-format reports**: Terminal Markdown preview + Excel (with embedded preview images) + HTML (with product images)

**How to trigger** (Chinese — the underlying platform is Chinese)

```
帮我找义乌购上的古风发簪货源，采购价要低
用义乌购选品：半导体散热风扇，适合跨境电商
帮我看看汉服发饰在义乌购上有什么供应商
```

**Usage examples**

```bash
# Single keyword search
python3 scripts/yiwugo_ai_api.py --keyword '古风发簪' --constraints '采购价低' --max-products 10 --no-answer

# Multi-keyword parallel search
python3 scripts/yiwugo_ai_api.py --keyword '半导体风扇' --keyword '制冷小风扇' --keyword '手持风扇' --sort score --max-products 15

# JSON output
python3 scripts/yiwugo_ai_api.py --keyword '汉服发饰' --constraints '低MOQ、不带电' --json
```

**Dependencies**

```bash
pip install openpyxl Pillow requests
```

**Platforms supported**: Amazon · TikTok Shop · Shopify · eBay · Shopee/Lazada · Temu

**🌐 Cross-platform**: Claude Code · Codex

→ [SKILL.md](./yiwugo-product-sourcing/SKILL.md) · [README](./yiwugo-product-sourcing/README.md)

</td></tr>
</table>

<table>
<tr><td>

### 📈 trend-to-creative-brief

Directly research public TikTok and Instagram posts for a specified date window and market, retain query, source date, engagement, market confidence, operation path, and billing metadata, then rank reusable mechanics by freshness, brand fit, and risk before producing original creative tests.

**Key capabilities**

- Direct public TikTok/Instagram operation discovery and bounded retrieval
- Auditable URLs, dates, engagement, queries, request IDs, and credits charged
- TikTok region filtering and explicit Instagram market uncertainty
- Original adaptations that preserve mechanics without copying protected expression
- Test questions, metrics, risks, review dates, and expiry

**Hard dependency**

Live retrieval requires [UnifAPI MCP](https://unifapi.com/mcp) at `https://mcp.unifapi.com`. Official setup uses read-only OAuth, requires no API key pasted into the skill, and bills by returned record. Without the MCP connection, the skill can only process evidence the user already supplied.

**🌐 Cross-platform**: Claude Code · Codex with MCP support

→ [SKILL.md](./trend-to-creative-brief/SKILL.md) · [README](./trend-to-creative-brief/README.md) · [Install UnifAPI MCP](https://unifapi.com/mcp)

</td></tr>
</table>

<table>
<tr><td>

### 🎙️ open-tiktok-script

Collect up to five public TikTok references, analyze hooks, pacing, demonstrations, and conversion mechanics with a configurable Gemini-compatible service, then create original Organic, TikTok Shop, Spark Ads, Paid In-Feed scripts, storyboards, and Creator Briefs.

**Key capabilities**

- Public competitor-video download and structured creative analysis
- Creator-native English writing instead of translated ecommerce hard-sell copy
- Organic, TikTok Shop, Spark Ads, Paid In-Feed, and Creator Brief formats
- Advertising-claim, copyright, body-image, protected-class, and cultural-context review
- Google Gemini by default, with configurable HTTP or HTTPS Gemini-compatible gateways

**Inspiration and attribution**

The six-step workflow and reference-library structure were inspired by [`huashu-douyin-script`](https://github.com/alchaincyf/huashu-skills/tree/master/huashu-douyin-script) by 花叔 ([`alchaincyf`](https://github.com/alchaincyf)). Permission to publish this adaptation has been confirmed, and attribution is preserved.

**🌐 Cross-platform**: Claude Code · Codex

→ [SKILL.md](./open-tiktok-script/SKILL.md) · [README](./open-tiktok-script/README.md) · [NOTICE](./open-tiktok-script/NOTICE.md)

</td></tr>
</table>

<table>
<tr><td>

### 📦 standard-product-image

Turn inconsistent supplier or phone photos into category-aware ecommerce white-background prompts or generated images. The workflow preserves visible colors, materials, logos, components, ports, and accessories, then checks the result for structural drift and invented details.

**Key capabilities**

- Category-aware rules plus a generic fallback
- Platform-specific sizing or safe portable defaults
- Product identity and hallucination acceptance checklist
- Prompt-only mode with no provider dependency

→ [SKILL.md](./standard-product-image/SKILL.md)

</td></tr>
</table>

<table>
<tr><td>

### 🔍 product-creative-scraper

> *"Competitor product images, selling points, and visual styles — batch scrape them, AI-analyze them, sync to Feishu Base for team review."*

Lightweight product creative scraping and analysis tool. Extracts product names, prices, and images from App Store, Google Play, Shopify/ecommerce product pages, then uses AI to analyze each image's selling points, style, layout, and scene. Outputs to Feishu Base or CSV.

**Key capabilities**

- **Multi-source scraping**: App Store, Google Play, Shopify stores, generic ecommerce product pages
- **Batch processing**: Single URL or multi-URL lists (CSV/TXT)
- **AI creative analysis**: OCR text extraction + VLM analysis for selling points, style, layout, scene type
- **Feishu Base output**: Two-table model (Products + Images) for team collaboration
- **Lightweight design**: No database, vector search, or Cloudflare infrastructure needed

**How to trigger**

```
帮我把这几个产品链接抓一下素材：https://...
分析一下这个 App Store 应用的截图卖点
帮我把竞品的产品图和卖点扒到飞书表格里
```

**Usage examples**

```bash
# Single URL
python3 scripts/run_product_scrape.py "https://apps.apple.com/app/xxx"

# Multiple URLs
python3 scripts/run_product_scrape.py --url-file urls.txt --format json

# AI analysis of scraped images
python3 scripts/analyze_assets.py --scrape-json scrape.json --format json

# Initialize Feishu Base
python3 scripts/init_lark_base.py --create --name "Product Creative Scraper MVP"

# Sync to Feishu
python3 scripts/sync_lark_base.py --scrape-json scrape.json --analysis-json analysis.json --project "Competitor Analysis"
```

**Dependencies**

```bash
pip install requests Pillow openpyxl
# For AI analysis
python3 scripts/configure_ai_gateway.py
```

**🌐 Cross-platform**: Claude Code · Codex

→ [SKILL.md](./product-creative-scraper/SKILL.md)

</td></tr>
</table>

<table>
<tr><td>

### 🎬 script-to-storyboard-video

A two-stage workflow for requests that already include an ad script: generate storyboard sheets from the script and product images, stop for human approval, then create vertical clips through user-configured NewAPI-compatible image and video endpoints. Use `product-to-ugc-video` instead when creator identity and continuous keyframes are the goal.

> Formerly `ad-storyboard-seedance`; existing installations should switch to the `script-to-storyboard-video` directory and skill name.

**Key capabilities**

- Automatic storyboard segmentation up to 15 seconds per segment
- Product fidelity and advertising-claim constraints
- Mandatory approval gate before paid video generation
- Dry-run, parallel generation, recovery artifacts, and ffprobe verification

→ [SKILL.md](./script-to-storyboard-video/SKILL.md)

</td></tr>
</table>

<table>
<tr><td>

### 📱 product-to-ugc-video

Build a character-consistent UGC project from a product image and description: creator planning, character reference, continuous keyframes, adjacent-frame video segments, manifests, logs, and optional merge metadata.

**Key capabilities**

- Neutral, user-controlled casting instead of hidden demographic defaults
- Character, wardrobe, product, and scene continuity
- Separately configurable planner, image, and video providers
- Offline heuristic planning and full dry-run
- Recoverable artifacts for targeted retries

→ [SKILL.md](./product-to-ugc-video/SKILL.md)

</td></tr>
</table>

<table>
<tr><td>

### 🎯 ad-campaign-workflow

> *"Got a product URL but don't know whether to run Meta or TikTok, what audiences to target, or what creatives to make? This skill generates the full strategy package."*

Platform-independent Meta and TikTok advertising workflow planner. Input a product URL or brief, get: strategy, audience targeting (both generic fields and motata CLI-consumable fields), campaign structures, ad copy, image prompts, and validation reports. **Does not create live ads or spend budget** — this is an analysis and preparation tool.

**Key capabilities**

- **Product analysis**: Auto-extracts selling points, audience hypotheses, use cases, and risk flags
- **Dual-platform audience targeting**: Generic targeting fields + motata platform-specific fields for both Meta and TikTok
- **Campaign structure generation**: Full Meta campaign/adset/ad and TikTok campaign/adgroup/ad hierarchies
- **Creative strategy**: Each ad gets angle, copy, CTA, landing URL, and image prompt
- **Validation report**: Auto-checks budget alignment, audience coverage, and creative parity
- **Google excluded**: Covers Meta + TikTok by default

**How to trigger**

```
帮我分析这个产品，出 Meta 和 TikTok 的投放方案：https://...
给这个产品做一套广告投放策略
帮我规划一下这个品的 Meta 受众定位
```

**Workflow**

1. **Analyze the product** — Read URL/brief, extract category, selling points, audience hypotheses
2. **Resolve targeting fields** — Query real Meta/TikTok targeting data via motata (requires tokens)
3. **Recommend strategy** — Countries, platform budget split, creative testing structure (user confirms)
4. **Generate campaign structures** — Full campaign/adset/ad or campaign/adgroup/ad
5. **Validate** — Check budget alignment, audience coverage, creative count parity

**Output sections**

- `strategy_brief` — Product, audience, channel, country, and budget rationale
- `targeting_fields_generic` — Generic targeting field bank
- `targeting_fields_motata` — motata-ready field bank with provenance
- `campaign_structure` — Meta and/or TikTok campaign hierarchy
- `creative_matrix` — Ad angles, copy, hooks, CTA, and audience mapping
- `image_prompt_pack` — One image prompt per ad
- `validation_report` — Checks passed, missing lookups, risk warnings, assumptions

**Safety rules**

- Read-only motata — never creates ads or spends budget
- All unresolved platform IDs explicitly marked — no fabricated IDs
- Campaign/adset/ad default status is draft or paused

**🌐 Cross-platform**: Claude Code · Codex

→ [SKILL.md](./ad-campaign-workflow/SKILL.md)

</td></tr>
</table>

---

## 🔗 Sourcing → Creative → Campaign Pipeline

These eight skills chain together across sourcing, creative preparation, and production:

```
yiwugo-product-sourcing     →  Find suppliers, get prices/MOQ/vendors
        ↓
product-creative-scraper    →  Analyze competitor creatives, extract selling points & styles
        ↓
standard-product-image      →  Standardize real product photos for ecommerce
        ↓
ad-campaign-workflow        →  Generate complete Meta/TikTok ad strategy package
        ↓
script-to-storyboard-video  →  Generate and approve storyboards from an existing script
        ↓
product-to-ugc-video        →  Produce UGC when creator continuity is required
```

---

## 🌟 About

A collection of practical skills accumulated from real cross-border ecommerce ad ops and product sourcing work. If they help you, a ⭐ is appreciated. Questions or suggestions welcome in Issues.

---

<div align="center">

[MIT License](./LICENSE) · Free to use, modify, and redistribute

</div>
