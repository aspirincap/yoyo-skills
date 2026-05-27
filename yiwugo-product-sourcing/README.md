<div align="center">

**中文** · [English](#-quick-start)

# 🛒 Yiwugo Product Sourcing

#### 义乌购 AI 选品助手 —— 跨境电商卖家的一站式货源发现工具

[![License](https://img.shields.io/badge/License-MIT-3B82F6?style=for-the-badge)](./LICENSE)
[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![AgentSkills](https://img.shields.io/badge/AgentSkills-Standard-8B5CF6?style=for-the-badge)](https://agentskills.io)

![Claude Code](https://img.shields.io/badge/Claude_Code-Skill-D97706?style=flat-square&logo=anthropic&logoColor=white)
![Codex](https://img.shields.io/badge/Codex-Skill-10B981?style=flat-square&logo=openai&logoColor=white)

</div>

---

## 这是什么

一个 API-first 的义乌购（Yiwugo）选品 Skill，**不需要打开浏览器**就能完成从关键词搜索 → AI 推荐 → 产品卡片拉取 → 交叉筛选 → Excel/HTML 报告输出的完整选品流程。

跨境电商卖家在做 Amazon、TikTok Shop、Shopify、eBay 选品时，最痛的就是"去义乌购翻几百页找货源"。这个 Skill 把整个流程自动化了：告诉它你想找什么，它直接给你一个带价格、MOQ、风险标记、优先级的货源短名单。

### 核心能力

- **AI 语义搜索**：用中文自然语言描述选品需求，义乌购 AI 自动匹配产品
- **产品卡片批量拉取**：无需登录，自动提取产品 ID 并通过 API 获取价格/MOQ/店铺信息
- **自动评分排序**：综合价格、MOQ、风险标记给出 Priority A/B/C/Avoid 分级
- **跨境外贸风险筛查**：自动标记带电、食品接触、儿童用品、品牌侵权等合规风险
- **三格式报告输出**：终端 Markdown 预览 + Excel（含预览图）+ HTML（含产品主图）
- **无需浏览器**：纯 API 调用，适合 CI/CD 或批量选品场景

---

## 快速开始

### 安装

在 Claude Code、Codex 等支持 Agent Skills 的 Agent 里，直接说：

```
帮我安装这个 skill：https://github.com/<your-username>/yiwugo-product-sourcing
```

或者手动 clone 到 skills 目录：

```bash
# Claude Code
git clone https://github.com/<your-username>/yiwugo-product-sourcing.git ~/.claude/skills/yiwugo-product-sourcing

# Codex
git clone https://github.com/<your-username>/yiwugo-product-sourcing.git ~/.codex/skills/yiwugo-product-sourcing
```

### 依赖

```bash
pip install openpyxl Pillow requests
```

### 基础用法

```bash
# 单关键词搜索
python3 scripts/yiwugo_ai_api.py --keyword '古风发簪' --constraints '采购价低' --max-products 10 --no-answer

# 多关键词并行搜索
python3 scripts/yiwugo_ai_api.py --keyword '半导体风扇' --keyword '制冷小风扇' --keyword '手持风扇' --sort score --max-products 15

# 输出 JSON（下游处理）
python3 scripts/yiwugo_ai_api.py --keyword '汉服发饰' --constraints '低MOQ、不带电' --json

# 指定输出路径
python3 scripts/yiwugo_ai_api.py --keyword '手机壳' --out-prefix ./reports/手机壳选品 --report-title '手机壳货源报告'
```

### 完整选品流程

1. **描述需求** → Agent 解析市场、平台、价格、类目约束
2. **构建中文查询** → 发送给义乌购 AI，获取推荐产品 ID
3. **拉取产品卡片** → 批量获取价格、MOQ、店铺、图片
4. **评分筛选** → 自动打分，标注风险（带电/食品/儿童/品牌）
5. **输出报告** → 终端预览 + Excel + HTML 三份报告

---

## 选品示例

### 半导体风扇

```bash
python3 scripts/yiwugo_ai_api.py \
  --keyword '半导体风扇' \
  --keyword '半导体散热风扇' \
  --keyword '半导体制冷风扇' \
  --constraints '采购价低、低MOQ、跨境外贸' \
  --sort score \
  --max-products 15 \
  --no-answer \
  --out-prefix ./半导体风扇 \
  --report-title '半导体风扇 - 义乌购货源短名单'
```

输出：15 款半导体风扇产品的打分排名、价格区间、MOQ、带电风险标记、Excel 和 HTML 报告。

### 汉服发饰

```bash
python3 scripts/yiwugo_ai_api.py --keyword '古风发簪' --keyword '汉服发饰' --constraints '采购价低' --sort score --max-products 10 --no-answer
```

---

## 触发词

### 中文
义乌购、选品、找货源、货源、进货、拿货、批发、采购、供应商、源头工厂、一件代发、跨境卖家进货、爆品测品、低MOQ

### English
product sourcing, supplier sourcing, wholesale sourcing, wholesale suppliers, procurement, product research, product discovery, buying goods, import sourcing, dropshipping sourcing, supplier shortlist, low MOQ, cross-border ecommerce sourcing

---

## 目录结构

```
yiwugo-product-sourcing/
├── SKILL.md                          # Agent Skills 标准入口
├── LICENSE
├── README.md
├── scripts/
│   └── yiwugo_ai_api.py             # 核心 Python 脚本（667行）
│                                     #   - SSE 流式调用义乌购 AI
│                                     #   - 自动提取 CSRF Token
│                                     #   - 产品卡片批量拉取
│                                     #   - 评分排序 & 风险标记
│                                     #   - Excel/HTML/Markdown 输出
├── references/
│   ├── evaluation-rubric.md         # 选品评分矩阵（价格/MOQ/物流/合规/差异化）
│   ├── prompt-templates.md          # 中文 Prompt 模板库
│   └── risk-checklist.md            # 跨境合规风险清单（带电/食品/儿童/品牌等）
└── agents/
    └── openai.yaml                  # Codex Agent 配置
```

---

## 适用平台

| 平台 | 典型选品场景 |
|---|---|
| **Amazon** | FBA 货源筛选、竞品价格对标、低MOQ测品 |
| **TikTok Shop** | 爆品选品、内容电商视觉化产品、低单价引流款 |
| **Shopify** | DTC 品牌货源、定制包装、小众利基品类 |
| **eBay** | 低价走量品、尾货清仓、多SKU铺货 |
| **Shopee/Lazada** | 东南亚热销品、轻小件、低价包邮款 |
| **Temu** | 极致低价、全托管供货、量大批采 |

---

## API 说明

| 端点 | 用途 | 是否需要登录 |
|---|---|---|
| `aiapi.yiwugo.com/forwebChat` | AI 语义搜索（SSE 流） | ❌ 不需要 |
| `www.yiwugo.com/api/product/aiGuideProducts.htm` | 批量获取产品卡片 | ❌ 需要 CSRF Token（从 `ai.html` 自动提取） |
| `www.yiwugo.com/product/detail/{id}.html` | 产品详情页（手动补充） | ❌ 不需要 |

### 注意事项

- 产品价格以"分"为单位返回（如 `600` = ¥6.00）
- `maxPrice` 可能为 `0`，视为无可用上限
- 复杂约束条件可能降低召回率；优先用短关键词搜索，本地筛选

---

## 🧠 为什么用 API 而不是浏览器

1. **速度快**：无浏览器启动开销，3 个关键词并行搜索 < 30 秒
2. **可自动化**：适合 CI/CD、定时选品任务、批量类目扫描
3. **结构化输出**：JSON/Markdown/Excel/HTML 直接可用
4. **低资源**：无头运行，VPS/容器友好

---

## 📄 License

MIT

---

## 🙏 致谢

- [义乌购](https://www.yiwugo.com/) — 全球小商品批发平台
- [Agent Skills](https://agentskills.io) — 开放标准
- [Khazix Skills](https://github.com/KKKKhazix/khazix-skills) — README 格式参考