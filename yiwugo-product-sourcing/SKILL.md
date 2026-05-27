---
name: yiwugo-product-sourcing
description: API-first Yiwugo/Yiwugou sourcing workflow for cross-border ecommerce product research, product selection, wholesale sourcing, and Yiwu supplier discovery. Use when the user mentions Yiwugo, Yiwugou, yiwugou, 义乌购, 选品, 找货源, 货源, 进货, 拿货, 批发, 采购, 供应商, 源头工厂, 一件代发, 跨境卖家进货, 爆品测品, 低MOQ, or asks for product links, supplier candidates, procurement keywords, target purchase prices, MOQ checks, light-small goods, and product risk screening for Amazon, TikTok Shop, Shopify, eBay, or international markets. Also trigger for English terms like product sourcing, supplier sourcing, wholesale sourcing, wholesale suppliers, procurement, product research, product discovery, buying goods, import sourcing, dropshipping sourcing, supplier shortlist, sourcing shortlist, wholesale price, low MOQ, and cross-border ecommerce sourcing.
---

# Yiwugo Product Sourcing

Use this skill to query Yiwugo AI and Yiwugo product-card APIs without Chrome, then turn the raw product IDs into a cross-border sourcing shortlist.

## Default Approach

Prefer the API-first script. For precise product searches, use short core keywords plus simple constraints. In commands below, set `SKILL_DIR` to this skill folder or replace it with the resolved skill path. By default, normal non-JSON runs print a Markdown terminal preview and write both `.xlsx` and `.html` report files. The Excel report embeds product preview images; the HTML report includes each product's main image.

```bash
python3 "$SKILL_DIR/scripts/yiwugo_ai_api.py" --keyword '古风发簪' --keyword '汉服发饰' --constraints '采购价低' --sort score --max-products 10 --no-answer
```

For one-off broad questions, pass a full Chinese message:

```bash
python3 "$SKILL_DIR/scripts/yiwugo_ai_api.py" '<Chinese sourcing query>'
```

Use Chrome only as a fallback when the API fails, the website changes, or the user explicitly asks to operate the browser.

## Workflow

### 1. Parse The Sourcing Brief

Extract the user's constraints:

- Target market and selling platform
- Season, use case, and product category
- Target selling price and procurement price
- Size, weight, and MOQ tolerance
- Battery/electrical/food-contact/children/IP risk tolerance
- Desired output format, such as links, table, or supplier questions

If enough information exists, proceed with reasonable assumptions and state them briefly. Ask only when the missing information would materially change the sourcing result.

### 2. Build The Yiwugo AI Query

Write Chinese prompts for Yiwugo AI. Use `references/prompt-templates.md` when a reusable template is helpful.

For broad product discovery, ask for product directions, procurement keywords, selling points, and risks.

For concrete sourcing, ask for direct Yiwugo clickable product links and include constraints such as low procurement price, low MOQ, light-small goods, non-battery, or target market.

Prefer one product keyword per API call. Avoid vague prompts like `找爆品`; use precise Chinese product names.

If an API call returns no product IDs, no products, or an apology instead of links, retry with a shorter core keyword and remove complex filters. For example, replace `汉服发簪 古风发簪 发钗，轻小件、适合海外、采购价低` with `古风发簪`, then screen the returned products locally. Try 2-3 synonym keywords such as `汉服发饰`, `古风发簪`, `新中式发饰`, or `团扇` before falling back to Chrome.

### 3. Query The API

Run the script from any working directory. It performs the full no-Chrome flow:

1. Calls `https://aiapi.yiwugo.com/forwebChat` as an SSE stream.
2. Reads the `final_answer` event.
3. Extracts product IDs from `<product>...</product>` tags.
4. Fetches `https://www.yiwugo.com/ai.html` to parse a fresh CSRF token.
5. Calls `https://www.yiwugo.com/api/product/aiGuideProducts.htm?ids=...`.
6. Prints a Markdown terminal preview or JSON.

Use `--json` when downstream processing is needed. The JSON includes `chats` and normalized `products` with URL, price range, MOQ, risk flags, heuristic score, and priority label:

```bash
python3 "$SKILL_DIR/scripts/yiwugo_ai_api.py" --keyword '古风发簪' --constraints '采购价低' --json
```

Useful options:

- `--keyword`: repeat for synonym/fallback searches; each keyword runs independently unless `--session-id` is provided.
- `--constraints`: keep short, such as `采购价低` or `低MOQ、不带电`. Complex constraints can reduce recall.
- `--sort score|price|ai`: default `score` combines price, MOQ, and risk flags.
- `--no-answer`: hide raw AI prose and print only session IDs plus the product table.
- `--max-products`: cap the de-duplicated table size.
- `--out-prefix`: choose where to write `.xlsx` and `.html` reports, without extension.
- `--markdown`: also write a `.md` report beside the default Excel and HTML reports.
- `--no-report-files`: print Markdown only and skip default Excel and HTML report files.
- `--report-title`: set the HTML report title.

Continue a conversation only when needed by passing the returned `session_id`:

```bash
python3 "$SKILL_DIR/scripts/yiwugo_ai_api.py" '<follow-up query>' --client-id '<same-client-id>' --session-id '<session-id>'
```

### 4. Score And Filter Candidates

The script now adds basic `risk_flags`, `score`, and `priority` labels (`A`, `B`, `C`, `Avoid`). Use these as a first pass, not a final sourcing decision. Then apply `references/evaluation-rubric.md` manually. At minimum, assess:

- Procurement cost and price range
- MOQ / start quantity
- Logistics friendliness
- Compliance risk
- Differentiation potential
- Supplier credibility signals from the product-card data

For detail fields not returned by the product-card API, fetch the HTML detail page directly:

```text
https://www.yiwugo.com/product/detail/{product_id}.html
```

Parse or inspect the page for dimensions, material, power source, shop age, service promises, phone/contact info, and update time.

### 5. Risk Screen Before Recommending

Use `references/risk-checklist.md`. Do not claim legal compliance unless certificates and market requirements are verified. Flag battery/electrical, food-contact, children's, medical, pest-control, branded, fragile, liquid, magnetic, or seasonal risks.

### 6. Output Format

Default script file output is dual-format:

- Excel: saved as `{prefix}.xlsx` with embedded product preview images, clickable product links, risk flags, priority labels, price, MOQ, shop fields, and metadata.
- HTML: saved as `{prefix}.html` with product main images, clickable product links, risk badges, priority labels, price, MOQ, and shop fields.

Markdown is still printed to stdout as a quick terminal preview. Use `--markdown` only when a saved `.md` file is explicitly useful.

For final user responses, summarize the best picks and link the generated HTML report path when available. For sourcing results, return a concise table:

| Priority | Product | Link | Price | MOQ | Why It Fits | Main Risk | Next Action |
|---|---|---|---:|---:|---|---|---|

Then add:

- Best 1-3 picks
- Products to avoid or verify carefully
- Supplier questions to ask before samples
- Follow-up query suggestions if results are too broad or too risky

## API Notes

- The AI SSE endpoint does not require login cookies in observed tests.
- The product-card endpoint rejects requests without a fresh `x-csrf-token`; the script extracts it from `window.__INITIAL_STATE__` in `ai.html`.
- Excel preview-image export requires `openpyxl` and `Pillow`; the script raises an install hint if either package is missing.
- Product prices are returned in cents/fen; convert `600` to `¥6.00`.
- `maxPrice` can be `0`; treat that as absent, not a valid upper bound.
- `userAgent` in the AI API query is a UUID-like client ID, not the browser User-Agent header.
- Ignore `router_token` and other internal planning events; use `final_answer` for user-facing content and product extraction.
- If a multi-condition search returns no products, retry with `--keyword '<short synonym>' --constraints '采购价低'` and filter locally.
