# Public TikTok and Instagram Research

Use this workflow when the user needs recent public TikTok or Instagram evidence. The public-data tools are the retrieval layer; this skill remains responsible for filtering, evidence quality, trend grouping and creative adaptation.

## Hard dependency and authentication

Live research requires the hosted [UnifAPI MCP](https://unifapi.com/zh/mcp) server at `https://mcp.unifapi.com`. Official setup uses OAuth and does not require pasting an API key into the skill. The connection is read-only and billed per returned public-data record.

Verify all three catalog tools exist before research:

- `mcp__unifapi__list_operations`
- `mcp__unifapi__get_operation`
- `mcp__unifapi__call_api`

If any tool is missing, OAuth is not connected, or the catalog lacks a requested platform operation, stop live retrieval and direct the user to the official setup page. Never fall back to another research skill or browser scraping without a new user request.

## Tool sequence

1. Call `mcp__unifapi__list_operations` with `search: "tiktok"` or `search: "instagram"`. Do not assume an endpoint exists from memory.
2. Prefer keyword-search operations that return public posts or videos. Current examples may include `/tiktok/search/videos` and `/instagram/search`, but catalog results are authoritative.
3. Call `mcp__unifapi__get_operation` for the chosen method/path. Inspect required parameters, maximum/default result size and billing.
4. Call `mcp__unifapi__call_api` with a concise topic query. For TikTok, pass an explicit small `limit` when supported. Instagram may not expose a limit.
5. Record the query, operation path, request ID, returned-record count and billing metadata.

## Cost and query discipline

Public operations may charge credits per returned record. Start with one query per requested platform. Use the smallest useful limit, normally 20 for TikTok. Make at most one refinement per platform when the first query is empty or mostly irrelevant. Do not paginate by default.

Use compact, behavior-oriented queries such as `night running gear`, `summer running essentials` or `desk setup reveal`. Avoid stuffing dates into the query because date filtering happens after retrieval.

## Date and market filtering

- Convert TikTok `create_time` and Instagram `taken_at` from Unix seconds to ISO dates.
- Keep only posts inside the requested inclusive date window.
- TikTok `region` is usable platform-supplied market evidence. A post matches US only when `region` is `US`.
- Instagram search commonly lacks a country field. Preserve `location.name` when present, but keep `market_status: unverified` unless the response supplies an explicit country match.
- Never infer US location from English, `#america`, a creator name or an audience assumption.

## Saving and normalization

Save the structured JSON response, not a screenshot or rendered tool output. Do not retain transient `play_url`, `video_url`, CDN cover/image URLs, avatars, cookies or authorization material. The bundled importer strips those fields from its normalized output.

```bash
python3 scripts/import_public_social.py \
  --input tiktok-response.json \
  --input instagram-response.json \
  --query "night running gear" \
  --query "night running gear" \
  --from-date 2026-07-01 \
  --to-date 2026-07-14 \
  --market US \
  --output 00_public_social_evidence.json
```

The number and order of `--query` values should match `--input`. Missing query labels are allowed but reduce auditability.

## Evidence interpretation

- Multiple independent creators using the same mechanic are stronger evidence than repeated posts from one seller.
- Engagement is observed context, not an expected ad result. Do not compare raw views across platforms as if definitions were identical.
- Search results are samples, not a complete platform census. Do not say a trend is platform-wide unless evidence supports that claim.
- Brand-owned, affiliate and `#ad` posts can reveal ad mechanics but provide weaker proof of organic adoption.
- If a requested platform returns no usable result, report zero coverage instead of substituting another platform silently.

## Handoff to creative analysis

Review normalized posts and create `trends.json` manually. Each trend should describe a reusable creative mechanic and cite at least one dated post. Include independent-source count, market confidence, paid/brand-owned concentration and any missing native proof in `uncertainty`.
