#!/usr/bin/env python3
"""Fetch Google SERPs from supported providers and emit a provider-neutral JSON file."""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TRANSIENT_CODES = {429, 500, 502, 503, 504}
SECRET_KEYS = {"api_key", "apikey", "authorization", "password", "x-api-key"}
SECRET_ENV_VARS = ("SERPER_API_KEY", "SERPAPI_API_KEY", "DATAFORSEO_LOGIN", "DATAFORSEO_PASSWORD")
COUNTRY_LOCATION_NAMES = {
    "us": "United States",
    "gb": "United Kingdom",
    "ca": "Canada",
    "au": "Australia",
    "de": "Germany",
    "fr": "France",
    "es": "Spain",
    "it": "Italy",
    "br": "Brazil",
    "mx": "Mexico",
    "jp": "Japan",
    "in": "India",
    "sg": "Singapore",
    "nl": "Netherlands",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def query_key(value: str) -> str:
    return clean_text(value).casefold()


def strip_secrets(value: Any, secret_values: tuple[str, ...]) -> Any:
    if isinstance(value, dict):
        output = {}
        for key, item in value.items():
            if str(key).casefold() in SECRET_KEYS:
                output[key] = "***redacted***"
            else:
                output[key] = strip_secrets(item, secret_values)
        return output
    if isinstance(value, list):
        return [strip_secrets(item, secret_values) for item in value]
    if isinstance(value, str):
        result = value
        for secret in secret_values:
            if secret:
                result = result.replace(secret, "***redacted***")
        return result
    return value


def request_json(
    *,
    safe_label: str,
    url: str,
    method: str,
    headers: dict[str, str],
    payload: Any | None,
    secrets: tuple[str, ...],
    timeout: float,
) -> Any:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read().decode("utf-8", errors="replace")
                return strip_secrets(json.loads(body), secrets)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:1200]
            safe_body = clean_text(strip_secrets(body, secrets))
            if exc.code in TRANSIENT_CODES and attempt < 3:
                retry_after = exc.headers.get("Retry-After") if exc.headers else None
                delay = min(float(retry_after), 30.0) if retry_after and retry_after.isdigit() else 2 ** (attempt - 1)
                time.sleep(delay)
                last_error = exc
                continue
            raise RuntimeError(f"{safe_label}: HTTP {exc.code}: {safe_body or 'no response body'}") from None
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            if attempt < 3:
                time.sleep(2 ** (attempt - 1))
                last_error = exc
                continue
            raise RuntimeError(f"{safe_label}: request or JSON parse failure: {clean_text(exc)}") from None
    raise RuntimeError(f"{safe_label}: request failed: {clean_text(last_error)}")


def organic_item(item: dict[str, Any], fallback_position: int) -> dict[str, Any]:
    url = clean_text(item.get("link") or item.get("url"))
    domain = clean_text(item.get("domain"))
    if not domain and url:
        domain = urllib.parse.urlsplit(url).netloc.lower()
    position = item.get("position") or item.get("rank_group") or item.get("rank_absolute") or fallback_position
    return {
        "position": position,
        "rank_absolute": item.get("rank_absolute"),
        "title": clean_text(item.get("title")),
        "url": url,
        "domain": domain,
        "displayed_url": clean_text(item.get("displayed_link") or item.get("breadcrumb")),
        "snippet": clean_text(item.get("snippet") or item.get("description")),
        "result_type": clean_text(item.get("type") or "organic"),
    }


def generic_question(item: Any) -> dict[str, Any]:
    if isinstance(item, str):
        return {"question": clean_text(item), "snippet": "", "title": "", "url": ""}
    if not isinstance(item, dict):
        return {"question": clean_text(item), "snippet": "", "title": "", "url": ""}
    expanded = item.get("expanded_element") if isinstance(item.get("expanded_element"), dict) else {}
    return {
        "question": clean_text(item.get("question") or item.get("title")),
        "snippet": clean_text(item.get("snippet") or expanded.get("description")),
        "title": clean_text(item.get("title")),
        "url": clean_text(item.get("link") or item.get("url")),
    }


def generic_related(item: Any) -> dict[str, str]:
    if isinstance(item, str):
        return {"query": clean_text(item)}
    if not isinstance(item, dict):
        return {"query": clean_text(item)}
    return {"query": clean_text(item.get("query") or item.get("keyword") or item.get("title") or item.get("text"))}


def normalize_common(
    *,
    provider: str,
    query: str,
    parent_query: str | None,
    discovery_source: str,
    depth: int,
    country: str,
    language: str,
    location: str | None,
    device: str,
    raw: dict[str, Any],
    organic: list[Any],
    paa: list[Any],
    related: list[Any],
    feature_map: dict[str, tuple[bool, Any]],
    secrets: tuple[str, ...],
) -> dict[str, Any]:
    organic_rows = [organic_item(item, idx) for idx, item in enumerate(organic, 1) if isinstance(item, dict)]
    paa_rows = [generic_question(item) for item in paa]
    related_rows = [generic_related(item) for item in related]
    paa_rows = [row for row in paa_rows if row["question"]]
    related_rows = [row for row in related_rows if row["query"]]
    features = {}
    for name, (available, feature_value) in feature_map.items():
        count = len(feature_value) if isinstance(feature_value, list) else (1 if feature_value else 0)
        features[name] = {"available": available, "present": bool(feature_value), "count": count}
    return {
        "query": query,
        "parent_query": parent_query,
        "discovery_source": discovery_source,
        "expansion_depth": depth,
        "provider": provider,
        "retrieved_at": utc_now(),
        "country": country,
        "language": language,
        "location": location,
        "device": device,
        "status": "ok",
        "organic_results": organic_rows,
        "people_also_ask": paa_rows,
        "related_searches": related_rows,
        "features": features,
        "raw_response": strip_secrets(raw, secrets),
    }


def fetch_serper(query: str, args: argparse.Namespace) -> dict[str, Any]:
    key = os.environ.get("SERPER_API_KEY", "")
    if not key:
        raise RuntimeError("SERPER_API_KEY is not configured")
    payload: dict[str, Any] = {"q": query, "gl": args.country, "hl": args.language, "page": 1}
    if args.location:
        payload["location"] = args.location
    if args.device:
        payload["device"] = args.device
    raw = request_json(
        safe_label=f"Serper query {query!r}",
        url="https://google.serper.dev/search",
        method="POST",
        headers={"X-API-KEY": key, "Content-Type": "application/json"},
        payload=payload,
        secrets=(key,),
        timeout=args.timeout,
    )
    if not isinstance(raw, dict):
        raise RuntimeError("Serper returned a non-object response")
    return normalize_common(
        provider="serper",
        query=query,
        parent_query=args._parent_query,
        discovery_source=args._discovery_source,
        depth=args._depth,
        country=args.country,
        language=args.language,
        location=args.location,
        device=args.device,
        raw=raw,
        organic=raw.get("organic") or [],
        paa=raw.get("peopleAlsoAsk") or [],
        related=raw.get("relatedSearches") or [],
        feature_map={
            "answer_box": ("answerBox" in raw, raw.get("answerBox")),
            "knowledge_graph": ("knowledgeGraph" in raw, raw.get("knowledgeGraph")),
            "shopping": ("shopping" in raw, raw.get("shopping")),
            "videos": ("videos" in raw, raw.get("videos")),
            "local": ("places" in raw, raw.get("places")),
            "top_stories": ("topStories" in raw, raw.get("topStories")),
            "people_also_ask": ("peopleAlsoAsk" in raw, raw.get("peopleAlsoAsk")),
            "related_searches": ("relatedSearches" in raw, raw.get("relatedSearches")),
        },
        secrets=(key,),
    )


def fetch_serpapi(query: str, args: argparse.Namespace) -> dict[str, Any]:
    key = os.environ.get("SERPAPI_API_KEY", "")
    if not key:
        raise RuntimeError("SERPAPI_API_KEY is not configured")
    params: dict[str, Any] = {
        "engine": "google",
        "q": query,
        "api_key": key,
        "gl": args.country,
        "hl": args.language,
        "start": 0,
        "device": args.device,
    }
    if args.location:
        params["location"] = args.location
    raw = request_json(
        safe_label=f"SerpApi query {query!r}",
        url="https://serpapi.com/search.json?" + urllib.parse.urlencode(params),
        method="GET",
        headers={"Accept": "application/json"},
        payload=None,
        secrets=(key,),
        timeout=args.timeout,
    )
    if not isinstance(raw, dict):
        raise RuntimeError("SerpApi returned a non-object response")
    if raw.get("error"):
        raise RuntimeError(f"SerpApi: {clean_text(strip_secrets(raw.get('error'), (key,)))}")
    return normalize_common(
        provider="serpapi",
        query=query,
        parent_query=args._parent_query,
        discovery_source=args._discovery_source,
        depth=args._depth,
        country=args.country,
        language=args.language,
        location=args.location,
        device=args.device,
        raw=raw,
        organic=raw.get("organic_results") or [],
        paa=raw.get("related_questions") or [],
        related=raw.get("related_searches") or [],
        feature_map={
            "answer_box": ("answer_box" in raw, raw.get("answer_box")),
            "knowledge_graph": ("knowledge_graph" in raw, raw.get("knowledge_graph")),
            "shopping": ("shopping_results" in raw, raw.get("shopping_results")),
            "videos": ("inline_videos" in raw, raw.get("inline_videos")),
            "local": ("local_results" in raw, raw.get("local_results")),
            "top_stories": ("top_stories" in raw, raw.get("top_stories")),
            "people_also_ask": ("related_questions" in raw, raw.get("related_questions")),
            "related_searches": ("related_searches" in raw, raw.get("related_searches")),
        },
        secrets=(key,),
    )


def _dataforseo_items(raw: dict[str, Any]) -> list[dict[str, Any]]:
    tasks = raw.get("tasks") or []
    if not tasks or not isinstance(tasks[0], dict):
        raise RuntimeError("DataForSEO response has no task")
    task = tasks[0]
    status_code = int(task.get("status_code") or 0)
    if status_code and status_code != 20000:
        raise RuntimeError(f"DataForSEO task {status_code}: {clean_text(task.get('status_message'))}")
    results = task.get("result") or []
    if not results or not isinstance(results[0], dict):
        return []
    return [item for item in (results[0].get("items") or []) if isinstance(item, dict)]


def fetch_dataforseo(query: str, args: argparse.Namespace) -> dict[str, Any]:
    login = os.environ.get("DATAFORSEO_LOGIN", "")
    password = os.environ.get("DATAFORSEO_PASSWORD", "")
    if not login or not password:
        raise RuntimeError("DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD are not configured")
    token = base64.b64encode(f"{login}:{password}".encode("utf-8")).decode("ascii")
    location_name = args.location or COUNTRY_LOCATION_NAMES.get(args.country.casefold())
    if not location_name:
        raise RuntimeError("DataForSEO requires --location for an unmapped country code")
    task = {
        "keyword": query,
        "location_name": location_name,
        "language_code": args.language,
        "device": args.device,
        "depth": 10,
    }
    raw = request_json(
        safe_label=f"DataForSEO query {query!r}",
        url="https://api.dataforseo.com/v3/serp/google/organic/live/advanced",
        method="POST",
        headers={"Authorization": f"Basic {token}", "Content-Type": "application/json"},
        payload=[task],
        secrets=(login, password, token),
        timeout=args.timeout,
    )
    if not isinstance(raw, dict):
        raise RuntimeError("DataForSEO returned a non-object response")
    top_status = int(raw.get("status_code") or 0)
    if top_status and top_status != 20000:
        raise RuntimeError(f"DataForSEO {top_status}: {clean_text(raw.get('status_message'))}")
    items = _dataforseo_items(raw)
    organic = [item for item in items if item.get("type") == "organic"]
    paa: list[Any] = []
    related: list[Any] = []
    for item in items:
        if item.get("type") == "people_also_ask":
            paa.extend(item.get("items") or [item])
        if item.get("type") == "related_searches":
            related.extend(item.get("items") or [item])
    types = {clean_text(item.get("type")) for item in items}
    return normalize_common(
        provider="dataforseo",
        query=query,
        parent_query=args._parent_query,
        discovery_source=args._discovery_source,
        depth=args._depth,
        country=args.country,
        language=args.language,
        location=location_name,
        device=args.device,
        raw=raw,
        organic=organic,
        paa=paa,
        related=related,
        feature_map={
            "answer_box": (True, [item for item in items if item.get("type") in {"answer_box", "featured_snippet"}]),
            "knowledge_graph": (True, [item for item in items if item.get("type") == "knowledge_graph"]),
            "shopping": (True, [item for item in items if item.get("type") in {"shopping", "paid"}]),
            "videos": (True, [item for item in items if "video" in clean_text(item.get("type"))]),
            "local": (True, [item for item in items if item.get("type") in {"local_pack", "maps_search"}]),
            "top_stories": (True, [item for item in items if item.get("type") in {"top_stories", "news"}]),
            "people_also_ask": (True, paa),
            "related_searches": (True, related),
        },
        secrets=(login, password, token),
    )


FETCHERS = {"serper": fetch_serper, "serpapi": fetch_serpapi, "dataforseo": fetch_dataforseo}


def expansion_candidates(entry: dict[str, Any], limit: int) -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    for item in entry.get("related_searches") or []:
        query = clean_text(item.get("query")) if isinstance(item, dict) else clean_text(item)
        if query:
            candidates.append((query, "related_search"))
    for item in entry.get("people_also_ask") or []:
        query = clean_text(item.get("question")) if isinstance(item, dict) else clean_text(item)
        if query:
            candidates.append((query, "people_also_ask"))
    seen: set[str] = set()
    output: list[tuple[str, str]] = []
    for query, source in candidates:
        key = query_key(query)
        if key and key not in seen:
            seen.add(key)
            output.append((query, source))
        if len(output) >= limit:
            break
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=sorted(FETCHERS), default="serper")
    parser.add_argument("--query", action="append", required=True, help="Seed query; repeat for multiple seeds")
    parser.add_argument("--country", default="us", help="Two-letter market code")
    parser.add_argument("--language", default="en", help="Language code")
    parser.add_argument("--location", help="Provider location name, such as 'United States'")
    parser.add_argument("--device", choices=["desktop", "mobile"], default="desktop")
    parser.add_argument("--expand-depth", type=int, choices=[0, 1], default=1)
    parser.add_argument("--max-expansions", type=int, default=8, help="Maximum expansions per seed")
    parser.add_argument(
        "--confirm-large-run",
        action="store_true",
        help="Confirm a planned run whose maximum call count exceeds ten paid SERP requests.",
    )
    parser.add_argument("--timeout", type=float, default=45.0)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    seeds: list[str] = []
    seen: set[str] = set()
    for raw_query in args.query:
        query = clean_text(raw_query)
        key = query_key(query)
        if query and key not in seen:
            seeds.append(query)
            seen.add(key)
    if not seeds:
        raise SystemExit("At least one non-empty --query is required")
    if args.max_expansions < 0 or args.max_expansions > 50:
        raise SystemExit("--max-expansions must be between 0 and 50")
    planned_max_calls = len(seeds) * (1 + args.max_expansions) if args.expand_depth == 1 else len(seeds)
    if planned_max_calls > 10 and not args.confirm_large_run:
        raise SystemExit(
            f"This run may make up to {planned_max_calls} paid SERP calls. "
            "Review the plan and rerun with --confirm-large-run after explicit user confirmation."
        )

    fetcher = FETCHERS[args.provider]
    entries: list[dict[str, Any]] = []
    failed: list[dict[str, str]] = []
    started_at = utc_now()

    def fetch(query: str, parent: str | None, source: str, depth: int) -> dict[str, Any] | None:
        args._parent_query = parent
        args._discovery_source = source
        args._depth = depth
        try:
            entry = fetcher(query, args)
            entries.append(entry)
            return entry
        except Exception as exc:  # Keep partial coverage explicit.
            secret_values = tuple(os.environ.get(name, "") for name in SECRET_ENV_VARS)
            diagnostic = clean_text(strip_secrets(exc, secret_values))
            failed.append({"query": query, "parent_query": parent or "", "diagnostic": diagnostic})
            print(f"warning: {diagnostic}", file=sys.stderr)
            return None

    seed_entries: list[tuple[str, dict[str, Any]]] = []
    for seed in seeds:
        entry = fetch(seed, None, "seed", 0)
        if entry:
            seed_entries.append((seed, entry))

    if args.expand_depth == 1:
        for seed, entry in seed_entries:
            for candidate, source in expansion_candidates(entry, args.max_expansions):
                key = query_key(candidate)
                if key in seen:
                    continue
                seen.add(key)
                fetch(candidate, seed, source, 1)

    output = {
        "schema_version": "1.0",
        "meta": {
            "provider": args.provider,
            "country": args.country,
            "language": args.language,
            "location": args.location,
            "device": args.device,
            "started_at": started_at,
            "completed_at": utc_now(),
            "seed_queries": seeds,
            "expand_depth": args.expand_depth,
            "max_expansions_per_seed": args.max_expansions,
            "successful_query_count": len(entries),
            "failed_query_count": len(failed),
            "partial": bool(failed),
        },
        "queries": entries,
        "failed_queries": failed,
    }
    path = Path(args.output).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(path), "successful": len(entries), "failed": len(failed)}, ensure_ascii=False))
    return 0 if entries else 2


if __name__ == "__main__":
    raise SystemExit(main())
