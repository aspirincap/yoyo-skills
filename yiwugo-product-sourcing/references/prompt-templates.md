# Prompt Templates

Use Chinese prompts with Yiwugo AI; it returns better product IDs and product cards.

## Broad Category Discovery

```text
我是跨境电商卖家，目标市场是{market}，平台是{platform}，想做{season}/{scenario}类轻小件，目标售价{selling_price_band}。请推荐适合从义乌采购的产品，并给出：产品方向、推荐理由、中文采购关键词、英文关键词、核心卖点、主要风险、适合人群。
```

## Specific Product Links

```text
请直接给我义乌购上具体可点击的商品链接：{keyword}。要求：{constraints}。请按采购价、起购量、轻小件程度、跨境适配度排序，并说明每个商品的推荐理由和风险。
```

## Low-Risk General Goods

```text
请筛选义乌购上{category}的具体商品链接，要求不带电、不带电池、不接触食品、不涉及儿童安全认证、不侵权，适合{market}跨境电商，采购价低，体积小。
```

## More Results / Pagination

```text
再推荐{n}个{keyword}，不要重复前面已经给过的商品，仍然要求{constraints}，优先低采购价和低起购量。
```

## Supplier Questions

```text
针对这些商品，请列出我联系义乌供应商时必须确认的问题：包装尺寸、单品重量、外箱规、是否可贴标、是否支持英文包装、样品费、MOQ、交期、是否有认证、是否支持跨境发货。
```


## CLI Keyword Search

Use this for stable API-first sourcing. Prefer short constraints and multiple synonym keywords.

```bash
python3 "$SKILL_DIR/scripts/yiwugo_ai_api.py"   --keyword '{keyword_1}'   --keyword '{keyword_2}'   --constraints '采购价低'   --sort score   --max-products 12   --no-answer
```

## Keyword Fallback Examples

- Hanfu theme: `古风发簪`, `汉服发饰`, `新中式发饰`, `古风团扇`, `香囊`
- Camping theme: `迷你露营灯`, `户外收纳袋`, `折叠水壶`, `露营餐具`
- Low-risk gift theme: `钥匙扣`, `贴纸`, `收纳袋`, `发夹`


## Report Output

Default non-JSON runs produce both Excel and HTML files. The Excel file embeds product preview images. Use `--out-prefix` to control the file names:

```bash
python3 "$SKILL_DIR/scripts/yiwugo_ai_api.py"   --keyword '{keyword}'   --constraints '采购价低'   --out-prefix './yiwugo_{slug}_report'   --report-title '{theme} 义乌购选品报告'
```

Use `--markdown` only when the caller also needs a saved Markdown file. Use `--no-report-files` only when the caller wants console Markdown without files. Use `--json` only for programmatic processing; JSON mode skips report file generation.
