---
name: product-creative-scraper
description: Use this skill when the user wants lightweight product, app, or ecommerce creative research from product URLs, App Store links, Google Play links, Shopify/generic ecommerce pages, or CSV/URL lists. It extracts product names, prices, and image URLs, then prepares image/copy analysis outputs without requiring a database, vector search, or Cloudflare infrastructure.
---

# Product Creative Scraper

## Purpose

Use this skill for a lightweight first-pass product creative scan. It is for quick research and structured outputs, not a persistent intelligence platform.

The bundled runner always uses `scripts/product_scraper.py`, which supports:

- App Store URLs
- Google Play URLs
- Shopify/generic ecommerce product pages
- Product pages with JSON-LD, OG meta, Shopify JS image arrays, or product-like HTML

Do not route scraping to external scraper files or fallback implementations; keep extraction behavior deterministic for publishing.

## Workflow

1. Normalize the user's input into URL tasks.
   - Accept a single URL, pasted URL list, or CSV/Excel-style list with a URL column.
   - If the user gives a keyword only, ask for permission to use a third-party search provider or ask them to provide URLs.
2. Run `scripts/run_product_scrape.py` against the URL tasks.
3. Review failed rows and retry only if the error looks transient.
4. Convert successful rows into a product creative table.
5. If the user asks for creative analysis, run `scripts/analyze_assets.py` on the extracted image URLs and add OCR/VLM fields.
6. Output Markdown, CSV, or Feishu Base fields depending on the user's request.

## Initialization

Commands below assume the current directory is this skill folder. Use one shared Feishu Base for all subsequent links:

```bash
python3 scripts/init_lark_base.py --show
```

Current shared Base config lives in `references/lark_base_config.json`.

Create a fresh shared Base and overwrite the local skill config:

```bash
python3 scripts/init_lark_base.py --create --name "Product Creative Scraper MVP"
```

If `LARK_BASE_TEMPLATE_TOKEN` or `--template-base-token` is provided, initialization copies that template without content. Otherwise it creates tables from scratch. Template copy is preferred when you have a known-good Base because some Feishu attachment fields created from scratch can be mobile-only.

Before creating or writing Base records, make sure user auth exists:

```bash
lark-cli auth login --domain base
```

## Script Usage

Single URL:

```bash
python3 scripts/run_product_scrape.py "https://example.com/products/item"
```

Multiple URLs:

```bash
python3 scripts/run_product_scrape.py --url-file urls.txt
```

JSON output:

```bash
python3 scripts/run_product_scrape.py --url-file urls.txt --format json
```

Analyze scraped images with OCR/VLM:

```bash
python3 scripts/analyze_assets.py --scrape-json scrape.json --format json
```

Use `--image-cache-dir` when attachments will be uploaded later; the analyzer writes `image_cache_path` so the upload step can reuse the same local files instead of downloading every image again. In `--mock` mode, passing `--image-cache-dir` still downloads/cache-images for pipeline tests while skipping model calls.

The analyzer uses `GEMINI_API_KEY` by default and the model in `GEMINI_VLM_MODEL`, falling back to `gemini-2.5-flash`. If `GEMINI_BASE_URL` is set, it calls that OpenAI-compatible base URL via `/v1/chat/completions`; otherwise it calls the official Google Gemini REST endpoint. Use `--mock` for local pipeline checks without calling a model.

Custom base URL:

```bash
export GEMINI_BASE_URL="https://your-openai-compatible-endpoint.example.com"
export GEMINI_API_KEY="..."
python3 scripts/analyze_assets.py --scrape-json scrape.json --model gemini-2.5-flash
```

## Output Contract

For exact fields, read `references/output_schema.md` when generating tables, CSV files, Feishu fields, or analysis reports. For OCR/VLM prompt details, read `references/prompt_templates.md`.

Minimum product output:

- `source_url`
- `source_type`
- `name`
- `price`
- `images`
- `status`
- `error`

Recommended creative analysis fields:

- `image_url`
- `image_type`
- `primary_selling_point`
- `secondary_selling_point`
- `style`
- `layout_type`
- `scene_type`
- `text_on_image_raw`
- `cn_copy_summary`
- `confidence`

## Feishu Output

For a first version, use the two-table Feishu model in `references/lark_base_schema.md`:

- `商品表`
- `图片表`

In this skill, `商品池` is implemented as `商品表`: one row per product/app URL. `图片表` is one row per image URL.

Do not create separate `卖点机会` or `风格分布` tables by default. Use Markdown summaries or Feishu filters/pivots over `图片表` unless the user explicitly asks for fixed summary tables.

Both tables have a `预览图` attachment field. Do not populate it with ordinary record writes; use `图片链接` by default, and upload real attachments only when the user explicitly requests image attachment uploads.

Upload real preview attachments from existing `图片链接` values:

```bash
python3 scripts/upload_preview_attachments.py --target all
```

When `analyze_assets.py` was run with `--image-cache-dir`, pass the same analysis JSON to avoid downloading images again:

```bash
python3 scripts/upload_preview_attachments.py --target all --analysis-json analysis.json
```

If Feishu returns `MOBILE_ONLY` for the attachment field, report that Base rejected API/CLI attachment cell writes and keep `图片链接` as the reliable image reference.

The upload script reports `cached_files_reused` and `images_downloaded`. For the no-redundant-download path, `images_downloaded` should be `0` when `--analysis-json` contains valid `image_cache_path` values.

Generate Feishu-ready CSV files:

```bash
python3 scripts/export_lark_tables.py \
  --scrape-json scrape.json \
  --analysis-json analysis.json \
  --project "Product Creative Scan" \
  --out-dir out
```

Append the same rows to the shared Feishu Base:

```bash
python3 scripts/sync_lark_base.py \
  --scrape-json scrape.json \
  --analysis-json analysis.json \
  --project "Product Creative Scan"
```

## Guardrails

- Do not build D1, Vectorize, R2, Queues, or Workflows for this skill.
- Do not promise long-term storage, semantic search, or similar-image search.
- Do not bypass private/login-only pages.
- Keep failures visible in the output instead of silently dropping them.
- Treat extracted images as remote references unless the user asks to download them.
- Do not silently fabricate OCR/VLM fields. If analysis fails, keep the image row and set `analysis_status=error`.
