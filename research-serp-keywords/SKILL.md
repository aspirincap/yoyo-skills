---
name: research-serp-keywords
description: Research keywords exclusively from live or exported search engine results pages (SERPs), normalize results from supported SERP APIs, expand seeds through People Also Ask and related searches, score SERP attainability, cluster queries by ranking-page overlap, and generate auditable Excel and HTML reports. Use when users ask for SERP keyword research, SERP competition analysis, PAA or related-query mining, search-intent mapping, content opportunities, keyword clustering, or Excel/HTML keyword reports without GSC, GA4, ad, ecommerce, search-volume, CPC, or third-party keyword-database data.
---

# Research SERP Keywords

Use SERP evidence as the only research input. Produce an Excel data workbook and a concise HTML decision report from the same normalized dataset.

## Guardrails

- Use only live SERP API responses or exported SERP responses. Do not call GSC, GA4, Ads, Shopify, marketplace, backlink, traffic-estimation, or keyword-volume sources.
- Never invent or proxy `search_volume`, `CPC`, or provider `KD`. Omit them from outputs.
- Name the deterministic metric `serp_opportunity_score`; never label it keyword difficulty or total SEO opportunity.
- Preserve provider, query, market, language, device, retrieval time, rank, URL, and evidence for every conclusion.
- Mark discovered PAA/related queries without their own fetched SERP as `discovered_only` and leave score/priority unscored.
- Treat provider features as observations, not ground truth. Surface missing features and partial responses.

## Workflow

### 1. Set the scope

Collect or infer:

- one or more seed queries;
- country/market and language;
- desktop or mobile;
- provider and available credential;
- expansion depth (`0` for seeds only, `1` for PAA/related-query expansion);
- maximum expansion calls and output directory.

Default to desktop, depth `1`, and at most eight expansion queries per seed. Before a paid run with more than ten total calls, state the planned maximum call count and obtain confirmation. Only then pass `--confirm-large-run`.

### 2. Select a SERP provider

Read [references/providers.md](references/providers.md) before a live call. Prefer an explicitly requested provider; otherwise select the first configured provider in this order: Serper, SerpApi, DataForSEO. Never print credentials.

### 3. Fetch and normalize SERPs

Run:

```bash
python3 "$SKILL_DIR/scripts/fetch_serp.py" \
  --provider serper \
  --query "custom pet portrait" \
  --country us \
  --language en \
  --device desktop \
  --expand-depth 1 \
  --max-expansions 8 \
  --output "$WORK_DIR/normalized-serp.json"
```

Use repeated `--query` flags for multiple seeds. Keep the normalized JSON as the audit source. On API failure, retry only transient errors; preserve successful queries and disclose partial coverage.

### 4. Analyze without non-SERP metrics

Read [references/scoring-and-quality.md](references/scoring-and-quality.md), then run:

```bash
python3 "$SKILL_DIR/scripts/analyze_serp.py" \
  --input "$WORK_DIR/normalized-serp.json" \
  --output "$WORK_DIR/serp-analysis.json"
```

Use ranking-page overlap for clusters. Use title saturation, domain diversity, platform dominance, PAA, result types, and SERP features for the score. Keep business relevance and demand explicitly outside scope.

### 5. Generate Excel and HTML

Read [references/output-contract.md](references/output-contract.md). Use the portable Python builder and public `openpyxl` dependency.

Copy the HTML asset to a writable work directory (optional; the builder can also read it directly):

```bash
cp "$SKILL_DIR/assets/report-template.html" "$WORK_DIR/report-template.html"
python3 "$SKILL_DIR/scripts/build_reports.py" \
  --input "$WORK_DIR/serp-analysis.json" \
  --template "$WORK_DIR/report-template.html" \
  --output-dir "$OUTPUT_DIR" \
  --base-name "serp_keyword_research" \
  --preview-dir "$WORK_DIR/previews"
```


### 6. Verify and deliver

- Inspect the generated workbook structure and formula allowlist emitted by the builder. The portable builder does not create PNG previews.
- Confirm Excel and HTML report the same query counts, priorities, top opportunities, provider, and caveats.
- Deliver the `.xlsx` and `.html`; summarize coverage and limitations in chat.

## Supported requests

- “研究这些种子词的 SERP，生成 Excel 和 HTML。”
- “挖掘 PAA 和 related searches，并按 SERP 可突破性排序。”
- “只基于 Google SERP 给关键词聚类，不要接 GSC 或搜索量工具。”
- “比较移动端和桌面端 SERP 格局。” Run each device as a separate dataset and label it explicitly.

## Failure behavior

- If no supported API credential or exported normalized SERP is available, stop before claiming research results and list the accepted credential variables from `providers.md`.
- If one query fails, continue when safe, mark the run partial, and list failed queries.
- If a provider omits PAA, shopping, local, or related-search fields, record them as unavailable rather than empty evidence.
- If no expansion query is fetched, include discovered candidates as unscored instead of borrowing the parent query's score.
