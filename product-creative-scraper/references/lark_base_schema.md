# Feishu Base Schema

This skill uses a lightweight two-table model.

Runtime config:

```text
references/lark_base_config.json
```

Run `scripts/init_lark_base.py --create` before syncing records. If `LARK_BASE_TEMPLATE_TOKEN` or `--template-base-token` is provided, the script copies that Base without content; otherwise it creates the two tables from scratch. Template copy is preferred when available because some Feishu attachment fields created from scratch can be mobile-only.

## 商品表

One row per product/app URL.

| Field | Type |
|---|---|
| 商品ID | text |
| 预览图 | attachment |
| 项目 | text |
| 来源类型 | select: ecommerce, appstore, googleplay, unknown |
| 商品名 | text |
| 商品链接 | url text |
| 价格 | number |
| 图片数量 | number |
| 抓取状态 | select: ok, error |
| 抓取错误 | text |
| 创建时间 | datetime |

## 图片表

One row per image URL.

| Field | Type |
|---|---|
| 图片ID | text |
| 预览图 | attachment |
| 商品ID | text |
| 商品名 | text |
| 商品链接 | url text |
| 图片序号 | number |
| 图片链接 | url text |
| 图片类型 | text |
| 主卖点 | text |
| 次卖点 | text |
| 风格 | text |
| 布局 | text |
| 场景 | text |
| 表达方式 | text |
| 图片文字 | text |
| 中文摘要 | text |
| 置信度 | number |
| 分析状态 | select: ok, error |
| 分析错误 | text |
| 是否参考 | select: 待定, 是, 否 |
| 人工备注 | text |

## Export

Use:

```bash
python3 scripts/export_lark_tables.py \
  --scrape-json scrape.json \
  --analysis-json analysis.json \
  --project "Project Name" \
  --out-dir out
```

The script writes:

- `products.csv` for 商品表
- `assets.csv` for 图片表

## Sync

Append rows directly into the shared Base:

```bash
python3 scripts/sync_lark_base.py \
  --scrape-json scrape.json \
  --analysis-json analysis.json \
  --project "Project Name"
```

The sync script uses `references/lark_base_config.json` and writes to the same Base every time.

## Preview Attachments

Both tables include an attachment field named `预览图`.

Do not write `预览图` through normal `record-upsert` or `record-batch-create`; Base attachment cells require `lark-cli base +record-upload-attachment` after a record exists.

Upload real preview attachments:

```bash
python3 scripts/upload_preview_attachments.py --target all
```

Behavior:

- `图片表`: uploads each row's `图片链接` into that row's `预览图`.
- `商品表`: uploads the first image from the matching product into that product row's `预览图`.
- Existing attachments are skipped unless `--force` is passed. Use `--force` carefully because Feishu can append another attachment instead of replacing the existing one.
- If `--analysis-json` contains valid `image_cache_path` values, cached local images are reused. The script reports `cached_files_reused` and `images_downloaded`; `images_downloaded=0` means the upload step did not re-download images.

Known Feishu limitation: some Base attachment fields return `MOBILE_ONLY: attachment field input is limited to mobile upload` even after the media file uploads successfully. When this happens, the script reports zero successful preview writes and keeps `图片链接` as the reliable preview/reference field.
