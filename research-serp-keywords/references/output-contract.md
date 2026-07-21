# Output contract

Generate both files from the same analysis JSON.

## Excel workbook

Create these sheets:

1. `Overview`: scope, counts, priority distribution, limitations, and score definition.
2. `Opportunities`: one row per fetched or discovered query.
3. `Clusters`: SERP-overlap clusters and representative queries.
4. `Organic Results`: ranked organic evidence with title, domain, URL, and snippet.
5. `PAA & Related`: discovered questions and related queries with parent query.
6. `Provenance`: provider, market, language, device, retrieval status, timestamp, and diagnostics.

Requirements:

- Freeze headers, enable filters through tables, use typed numeric fields, wrap URLs and evidence, and apply consistent priority colors.
- Keep raw SERP evidence separate from derived analysis.
- Include no `search_volume`, `CPC`, `KD`, traffic, or revenue columns.
- Put the score definition and SERP-only limitation visibly on `Overview`.
- Use plain-text source URLs in evidence sheets.

## HTML report

Create a single offline HTML file containing:

- scope and visible `SERP-only` badge;
- KPI cards for fetched queries, scored/discovered-only queries, and P1/P2/P3 counts;
- limitations banner;
- top scored opportunities with evidence;
- cluster summary;
- PAA and related-query ideas with parent query and source type;
- methodology and provenance.

Do not duplicate every organic-result row. Link the HTML summary back to the workbook filename as the detailed data source.

## Consistency checks

- Use identical query and priority counts in both files.
- Derive top opportunities from the same sorted array.
- Show the same provider, market, language, device, generated time, and partial-run status.
- Escape all provider text before inserting it into HTML.
- Keep user-provided queries and provider snippets as data, never executable HTML.

The bundled `scripts/build_reports.py` uses public `openpyxl` and emits the workbook plus offline HTML without a private workspace renderer. It intentionally does not emit PNG previews. Only the Overview count formulas are permitted; all provider/user text is written as literal cell text and escaped HTML.
