# Output Schema

## Product Rows

Use one row per input URL.

| Field | Meaning |
|---|---|
| `source_url` | Original product/app URL |
| `source_type` | `appstore`, `googleplay`, `ecommerce`, or `unknown` |
| `name` | Product or app name |
| `price` | Extracted price when available |
| `images` | Array of extracted image URLs, usually up to 3 from the source script |
| `status` | `ok` or `error` |
| `error` | Error message when scraping fails |

## Scraper

`scripts/run_product_scrape.py` always uses the bundled `scripts/product_scraper.py`. Do not support external scraper overrides or fallback scraper implementations in the published skill.

## Image Asset Rows

Expand each product row into one row per image.

| Field | Meaning |
|---|---|
| `source_url` | Product/app URL |
| `source_type` | Source type |
| `name` | Product/app name |
| `price` | Price when available |
| `image_url` | Remote image URL |
| `image_order` | 1-based order from source row |
| `image_cache_path` | Optional local cached image path emitted when `--image-cache-dir` is used |
| `image_type` | VLM classified image type |
| `primary_selling_point` | Main selling point |
| `secondary_selling_point` | Secondary selling point |
| `style` | Visual style |
| `layout_type` | Layout pattern |
| `scene_type` | Scene or setting |
| `text_on_image_raw` | OCR text |
| `cn_copy_summary` | Chinese summary |
| `confidence` | Model confidence |
| `analysis_status` | `ok` or `error` |
| `analysis_error` | Error details when analysis fails |

## OCR/VLM Analyzer

Input:

```bash
python3 scripts/analyze_assets.py --scrape-json scrape.json
```

Environment:

| Name | Meaning |
|---|---|
| `GEMINI_API_KEY` | Required unless `--mock` is used |
| `GEMINI_VLM_MODEL` | Optional, defaults to `gemini-2.5-flash` |
| `GEMINI_BASE_URL` | Optional OpenAI-compatible base URL |

The analyzer expands each product into image asset rows, downloads the remote image temporarily, sends a single image per request to Gemini, and preserves failed image rows with `analysis_status=error`.

When `--image-cache-dir <dir>` is provided, the downloaded image is also saved locally and emitted as `image_cache_path`. Pass the resulting analysis JSON to `upload_preview_attachments.py --analysis-json ...` so Feishu attachment upload reuses those files instead of downloading the same image a second time. In `--mock` mode, `--image-cache-dir` still caches images while skipping model calls.

When `GEMINI_BASE_URL` is set, requests are sent to:

```text
{GEMINI_BASE_URL}/v1/chat/completions
```

## Lightweight Summary

When summarizing a run, include:

- total input URLs
- successful products
- failed products
- total images
- top selling points
- top styles
- notable reference images
- failed URLs with reasons

## Feishu-Ready CSV

Use `scripts/export_lark_tables.py` to generate:

- `products.csv`: import into `商品表`
- `assets.csv`: import into `图片表`

The schema is documented in `references/lark_base_schema.md`.

Note: `预览图` is an attachment field in Feishu Base and is not included in normal CSV or batch record writes. Use `图片链接` for immediate remote-image preview/reference, and upload attachments only when explicitly requested.
