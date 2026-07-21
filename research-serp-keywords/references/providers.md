# Supported SERP providers

Use only these live SERP connectors. Check the provider's official documentation at execution time because endpoints, quotas, and response fields can change.

## Selection

1. Honor the provider named by the user.
2. Otherwise select the first configured credential: Serper, SerpApi, DataForSEO.
3. Do not mix providers within one report unless the user explicitly requests a provider comparison.
4. Record the provider and raw retrieval timestamp for every query.

## Serper

- Credential: `SERPER_API_KEY`
- Endpoint: `POST https://google.serper.dev/search`
- Authentication: `X-API-KEY` header
- Core request fields: `q`, `gl`, `hl`, `page`, `device`; use pages rather than assuming a configurable result count
- Normalized response fields: `organic`, `peopleAlsoAsk`, `relatedSearches`, `answerBox`, `knowledgeGraph`, `shopping`, `videos`, `places`
- Official docs: <https://serper.dev/>

## SerpApi

- Credential: `SERPAPI_API_KEY`
- Endpoint: `GET https://serpapi.com/search.json`
- Authentication: `api_key` query parameter
- Core request fields: `engine=google`, `q`, `gl`, `hl`, `start`, `device`; advance `start` by page rather than assuming a configurable result count
- Normalized response fields: `organic_results`, `related_questions`, `related_searches`, `answer_box`, `knowledge_graph`, `shopping_results`, `inline_videos`, `local_results`
- Official docs: <https://serpapi.com/search-api>

## DataForSEO SERP

- Credentials: `DATAFORSEO_LOGIN`, `DATAFORSEO_PASSWORD`
- Endpoint: `POST https://api.dataforseo.com/v3/serp/google/organic/live/advanced`
- Authentication: HTTP Basic authentication
- Core task fields: `keyword`, `location_name` or `location_code`, `language_code`, `device`, `depth`
- Normalized response path: `tasks[].result[].items[]`, interpreted by item `type`
- Official docs: <https://docs.dataforseo.com/v3/serp/google/organic/live/advanced/>

## Query-budget rules

- Count one provider request per queried SERP unless provider documentation says otherwise.
- Expansion depth `1` queries PAA and related-search candidates after seed retrieval; it therefore increases cost.
- Deduplicate queries case-insensitively before calling the provider.
- Cap the default at eight expansion calls per seed.
- Retry HTTP `429`, `500`, `502`, `503`, and `504` up to three times with bounded backoff.
- Do not retry authentication, invalid-parameter, or insufficient-credit errors.

## Secret handling

- Read credentials only from environment variables.
- Never write credentials to normalized JSON, report files, command output, or logs.
- Redact response request URLs when a provider uses a query-parameter API key.
