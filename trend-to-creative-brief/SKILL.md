---
name: trend-to-creative-brief
description: Directly research recent public TikTok and Instagram posts, or accept supplied social/search/creator/commerce evidence, then turn it into a brand-specific creative testing brief with source strength, freshness, market confidence, brand fit, adaptation logic, expiry, risks, hooks, formats, and experiments. Use whenever the user asks what is trending on TikTok or Instagram, requests recent social evidence for a market or date window, wants to rank trends for a product, or needs original ad/organic concepts without blindly copying creators.
license: MIT
---

# Trend to Creative Brief

Convert trend evidence into an actionable, brand-safe creative test plan. Discovery and adaptation are separate jobs: a popular format is not automatically right for a brand.

Offline normalization and user-supplied evidence use Python 3.10+ standard library only. Live TikTok/Instagram research has the hard MCP dependency described below.

## Hard Dependency: UnifAPI MCP

Live TikTok and Instagram discovery requires [UnifAPI MCP](https://unifapi.com/zh/mcp). The hosted server is `https://mcp.unifapi.com`; it uses OAuth, is read-only and charges by returned public-data record. This skill does not receive, store or ask the user to paste an UnifAPI key.

Before any live research, run this dependency gate:

1. Confirm `mcp__unifapi__list_operations`, `mcp__unifapi__get_operation` and `mcp__unifapi__call_api` are available.
2. Call `list_operations` with the broad searches `tiktok` and `instagram`.
3. Confirm the catalog exposes a usable public-post search operation for every requested platform. Current expected paths are `/tiktok/search/videos` and `/instagram/search`, but the live catalog is authoritative.
4. Call `get_operation` for each selected path and inspect parameters and billing before retrieving records.
5. If tools are missing, OAuth fails, or a requested platform has no search operation, stop live discovery. Tell the user exactly which check failed and link to `https://unifapi.com/zh/mcp`. Do not silently substitute browser scraping or another research skill.

The dependency gate is not required when the user already supplied evidence and only wants scoring or creative adaptation. See `README.md` and `references/public-social-research.md` for setup and failure behavior.

## Boundary

This skill does not scrape platforms, bypass login, or claim access to unavailable native data. Accept:

- public TikTok/Instagram results returned by the authorized public-data catalog;
- user-provided trend notes or URLs;
- outputs from authorized research tools;
- official platform trend centers;
- reputable industry/media/community sources, clearly labeled.

When native evidence is unavailable, say so and lower confidence. Do not disguise a media article as platform-native proof.

## Inputs

Collect:

- brand, product, market, audience, positioning, proof assets and constraints;
- target platforms and organic/ad objective;
- trend observation window and `as_of` date;
- each trend's title, mechanics, format, platform, tags, observed date and sources;
- claims, topics, creators, music, IP or cultural contexts to avoid.

Read `references/evidence-and-scoring.md` before rating trends. Read `references/creative-adaptation.md` before producing hooks or scripts.

If the user asks for recent TikTok or Instagram discovery, read `references/public-social-research.md` and query the authorized public-data catalog directly. This skill has no dependency on another research skill.

## Workflow

### 1. Discover public posts when needed

Pass the UnifAPI dependency gate above, then use its operation catalog rather than guessing endpoints:

1. Search the catalog for TikTok and Instagram operations.
2. Inspect the selected operation schema and billing before calling it.
3. Run one bounded broad query per requested platform; make at most one narrower refinement when the first result is empty or mostly irrelevant.
4. Preserve the operation path, query, billing, requested date window and target market.
5. Filter dates and market evidence before treating a post as relevant.

Do not paginate or run many query variations unless the user explicitly requests comprehensive research. Public operations may charge credits per returned record.

### 2. Normalize public results

Save only the structured API response JSON to temporary input files, then run:

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

The importer removes transient signed media URLs, deduplicates posts, filters the date range and preserves citations, engagement, platform region/location evidence and billing metadata. TikTok `region=US` is usable market evidence. Instagram search results often lack a reliable country field; mark them `unverified` rather than inferring US geography from English text or hashtags.

### 3. Group evidence into trends

Create `01_trend_evidence.json` using `references/schemas.md`.

- Give every trend a stable ID.
- Record observation and source publication dates separately.
- Label source type: `native`, `official`, `industry`, `media`, `community`, or `unknown`.
- Describe the repeatable mechanic rather than only the trend name.
- Record uncertainty, missing independent proof and geographic/language scope.
- Group posts by repeatable mechanic, not merely shared hashtags or product category.
- Treat several posts from one seller as repeated execution, not independent platform validation.
- Keep weak or off-market examples as directional evidence only.

### 4. Check freshness

Estimate the trend's useful life from its evidence and format. A short audio/meme may expire in days; a durable creator format or search behavior may last longer.

Set:

- `observed_at`;
- `expires_at` or review date;
- `freshness_status`: `fresh`, `aging`, `stale`, or `unknown`.

Never call something “trending now” without a date and evidence within the user's requested window.

### 5. Evaluate brand fit

Score and explain:

- audience relevance;
- product/use-case relevance;
- platform fit;
- proof availability;
- brand-tone fit;
- legal, cultural, IP, claim and execution risk.

Choose one decision:

- `pursue`: strong evidence and natural fit;
- `adapt`: useful mechanic but expression needs a brand-specific change;
- `watch`: insufficient evidence or uncertain timing;
- `skip`: weak fit, stale, unsafe or dependent on copying protected expression.

The explanation matters more than the number.

### 6. Build original adaptations

For each `pursue` or `adapt` trend, produce 2–3 creative angles. Preserve the mechanic, not another creator's exact script, footage, character, music, artwork or catchphrase.

Each angle needs:

- hook;
- product truth or proof;
- beat structure;
- recommended format and duration;
- creator/brand role;
- CTA or organic ending;
- what makes it distinct from the source trend;
- assets needed and claims requiring verification.

### 7. Design tests

Build a compact matrix that changes one major variable at a time:

- hook;
- creator framing;
- proof/demo;
- pacing;
- CTA;
- Reels/TikTok/Shorts versus carousel adaptation.

Do not invent expected performance. State the learning question and success metric the user should measure.

### 8. Produce the brief

Create:

```text
00_public_social_evidence.json (when direct discovery was used)
01_trend_evidence.json
02_trend_scorecard.json
03_creative_brief.md
04_test_matrix.csv or .json
05_risks_and_expiry.md
```

Use `scripts/build_brief.py` when normalized brand and trend JSON are available:

```bash
python3 scripts/build_brief.py \
  --brand brand.json \
  --trends trends.json \
  --as-of 2026-07-14 \
  --output-dir outputs/trend-brief
```

The deterministic builder ranks evidence, freshness and basic keyword/platform fit. Treat its score as a consistency aid, then apply human/agent judgment to cultural fit and creative quality.

## Report Structure

```markdown
# Trend-to-Creative Brief

## Decision Summary
| trend | decision | confidence | expiry | reason |

## Recommended Creative Angles
### [Trend]
- Mechanic:
- Brand adaptation:
- Hook:
- Proof:
- Beats:
- Format:
- Distinctive change:
- Risks:

## Test Matrix

## Watch / Skip

## Evidence and Limitations
```

## Quality Rules

- Cite source URLs and dates for every trend decision.
- Report the queries, result counts, date filter, market-confidence rule and credits charged when direct discovery was used.
- Distinguish observed engagement from inferred creative potential.
- Do not copy protected expression or rely on unlicensed music/footage.
- Reject a trend when the brand fit is forced.
- Make expiry visible so old briefs are not reused as current intelligence.
- Mark claims and cultural interpretations that require review.

Run `python3 tests/test_smoke.py` for offline verification.
