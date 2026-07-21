# SERP scoring and quality rules

## Scope

Score only the apparent attainability and format opening visible in one SERP snapshot. Do not interpret the score as demand, traffic potential, revenue potential, keyword difficulty, or business priority.

## `serp_opportunity_score`

Calculate a 0–100 score from auditable SERP features:

```text
35 base
+ 0–25 domain diversity among organic results
+ 0–15 low exact-title saturation
+ 0–10 result-format opening
+ 0–5 PAA evidence
+ 0–5 limited UGC/forum opening
- 0–20 dominant-platform concentration
- 0–5 shopping saturation
```

Definitions:

- Domain diversity: `unique organic domains / organic result count × 25`.
- Exact-title saturation: compare normalized query tokens with result-title tokens; reward low saturation because fewer pages directly target the query.
- Result-format opening: reward a recognizable content format with no single format occupying most organic results.
- PAA evidence: add five when the provider returns at least one PAA item.
- UGC/forum opening: add five when one to three top-ten results are Reddit, Quora, or a forum; add zero when none or when the SERP is already dominated by them.
- Dominant-platform concentration: subtract up to twenty in proportion to top-ten results from large marketplaces, social/video platforms, encyclopedias, and major aggregators.
- Shopping saturation: subtract five when shopping results are present and transactional platforms also dominate organic results.

Clamp the result to 0–100 and round to one decimal.

## SERP priority

- `P1`: score at least 70.
- `P2`: score from 50 through 69.9.
- `P3`: score below 50.
- `Unscored`: the query was discovered but its own SERP was not fetched or had fewer than three organic results.

Call this `serp_priority`, not content priority or overall SEO priority.

## Intent and format

Infer intent conservatively from query wording and returned features:

- `local`: local pack or “near me” pattern.
- `transactional`: buy/order/price/deal wording plus shopping or product results.
- `commercial`: best/review/vs/alternative/comparison wording or comparison-heavy results.
- `informational`: question wording, how-to patterns, definitions, or guide-heavy results.
- `mixed`: conflicting evidence.

Record `intent_basis` as a short evidence string. Do not claim an API-provided intent unless the provider returned one explicitly.

## SERP-overlap clustering

For each fetched query, compare the sets of normalized top-ten organic URLs. Join two queries when either condition holds:

- at least three URLs overlap; or
- overlap coefficient is at least 0.35.

Use connected components as clusters. Label a cluster with its highest-scoring query. Attach unqueried PAA/related candidates to the parent query's cluster and keep them unscored.

## Data-quality requirements

- Normalize URLs by lowercasing the host, removing fragments, removing common tracking parameters, and trimming trailing slashes.
- Preserve original URLs separately.
- Treat absent provider fields as `unavailable`; do not assume a feature was absent from the real SERP.
- Mark fewer than three organic results as insufficient for scoring.
- Include retrieval time, country, language, device, provider, parent query, and discovery source.
- Preserve failed-query diagnostics without secrets.
