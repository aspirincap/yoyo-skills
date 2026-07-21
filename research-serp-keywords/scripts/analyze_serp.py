#!/usr/bin/env python3
"""Analyze normalized SERP JSON without introducing non-SERP metrics."""

from __future__ import annotations

import argparse
import json
import re
import urllib.parse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "best", "by", "for", "from", "how", "i",
    "in", "is", "it", "of", "on", "or", "that", "the", "this", "to", "vs", "what", "when",
    "where", "which", "who", "why", "with", "you", "your",
}
PLATFORM_SUFFIXES = {
    "amazon.com", "etsy.com", "walmart.com", "ebay.com", "youtube.com", "tiktok.com", "pinterest.com",
    "wikipedia.org", "facebook.com", "instagram.com", "linkedin.com", "quora.com", "reddit.com",
}
FORUM_SUFFIXES = {"reddit.com", "quora.com", "stackexchange.com", "stackoverflow.com"}
TRACKING_KEYS = {"gclid", "fbclid", "msclkid", "ref", "ref_", "source"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def key_text(value: str) -> str:
    return clean_text(value).casefold()


def domain_of(url: str, supplied: str = "") -> str:
    domain = clean_text(supplied).casefold().split(":")[0].strip(".")
    if not domain:
        domain = urllib.parse.urlsplit(clean_text(url)).netloc.casefold().split(":")[0].strip(".")
    return domain[4:] if domain.startswith("www.") else domain


def normalize_url(url: str) -> str:
    text = clean_text(url)
    if not text:
        return ""
    try:
        parts = urllib.parse.urlsplit(text)
        host = domain_of(text)
        path = re.sub(r"/+", "/", parts.path or "/")
        if path != "/":
            path = path.rstrip("/")
        query = []
        for key, value in urllib.parse.parse_qsl(parts.query, keep_blank_values=True):
            lower = key.casefold()
            if lower.startswith("utm_") or lower in TRACKING_KEYS:
                continue
            query.append((key, value))
        query.sort()
        return urllib.parse.urlunsplit((parts.scheme.casefold() or "https", host, path, urllib.parse.urlencode(query), ""))
    except Exception:
        return text


def tokens(text: str) -> set[str]:
    found = re.findall(r"[\w\u4e00-\u9fff]+", clean_text(text).casefold(), flags=re.UNICODE)
    return {token for token in found if len(token) > 1 and token not in STOPWORDS}


def domain_matches(domain: str, suffixes: set[str]) -> bool:
    return any(domain == suffix or domain.endswith("." + suffix) for suffix in suffixes)


def classify_result(title: str, snippet: str, domain: str) -> str:
    text = f"{title} {snippet}".casefold()
    if domain_matches(domain, FORUM_SUFFIXES) or any(term in text for term in ("forum", "community", "discussion")):
        return "forum"
    if domain in {"youtube.com", "vimeo.com", "tiktok.com"} or any(term in text for term in ("video", "watch")):
        return "video"
    if any(term in text for term in ("best ", " vs ", "review", "comparison", "alternatives")):
        return "comparison"
    if any(term in text for term in ("buy ", "shop ", "price", "product", "collection", "category")):
        return "commerce"
    if any(term in text for term in ("how to", "guide", "tutorial", "explained", "what is", "learn")):
        return "guide"
    return "other"


def infer_intent(query: str, feature_names: set[str], result_types: Counter[str]) -> tuple[str, str]:
    text = key_text(query)
    if "local" in feature_names or "near me" in text:
        return "local", "local pack or local wording"
    if any(term in text for term in ("buy", "order", "price", "deal", "coupon", "shop")) and (
        "shopping" in feature_names or result_types.get("commerce", 0) > 0
    ):
        return "transactional", "transaction wording with commerce SERP evidence"
    if "shopping" in feature_names or result_types.get("commerce", 0) >= 2:
        return "commercial", "shopping feature or commerce-heavy organic results"
    if any(term in text for term in ("best", "review", " vs ", "versus", "alternative", "compare", "comparison")) or result_types.get("comparison", 0) >= 2:
        return "commercial", "comparison wording or comparison-heavy results"
    if re.match(r"^(how|what|why|when|where|who|can|does|is|are)\b", text) or result_types.get("guide", 0) >= 2:
        return "informational", "question wording or guide-heavy results"
    return "mixed", "no single intent dominates visible SERP evidence"


def content_recommendation(intent: str, result_types: Counter[str], paa: list[dict[str, Any]], query: str) -> tuple[str, str]:
    if intent == "local":
        content_type = "local landing page"
    elif intent == "transactional":
        content_type = "category or product landing page"
    elif intent == "commercial":
        content_type = "comparison or buying guide"
    elif result_types.get("forum", 0) >= 2:
        content_type = "expert first-hand answer"
    else:
        content_type = "guide or FAQ"
    if paa:
        angle = f"Answer the visible PAA question: {clean_text(paa[0].get('question'))}"
    elif result_types:
        dominant = result_types.most_common(1)[0][0]
        angle = f"Create a {content_type} that is more specific and evidence-led than the dominant {dominant} results for “{query}”."
    else:
        angle = f"Collect a complete SERP before choosing a content angle for “{query}”."
    return content_type, angle


def analyze_query(entry: dict[str, Any]) -> dict[str, Any]:
    query = clean_text(entry.get("query"))
    organic = [row for row in (entry.get("organic_results") or []) if isinstance(row, dict)][:10]
    paa = [row for row in (entry.get("people_also_ask") or []) if isinstance(row, dict)]
    features = entry.get("features") or {}
    present_features = {name for name, value in features.items() if isinstance(value, dict) and value.get("present")}
    domains = [domain_of(row.get("url", ""), row.get("domain", "")) for row in organic]
    domains = [domain for domain in domains if domain]
    unique_domains = sorted(set(domains))
    result_types = Counter(
        classify_result(clean_text(row.get("title")), clean_text(row.get("snippet")), domain_of(row.get("url", ""), row.get("domain", "")))
        for row in organic
    )
    q_tokens = tokens(query)
    exact_title_count = 0
    for row in organic:
        title_tokens = tokens(clean_text(row.get("title")))
        coverage = len(q_tokens & title_tokens) / max(len(q_tokens), 1)
        if coverage >= 0.8:
            exact_title_count += 1
    n = len(organic)
    platform_count = sum(domain_matches(domain, PLATFORM_SUFFIXES) for domain in domains)
    forum_count = sum(domain_matches(domain, FORUM_SUFFIXES) for domain in domains)
    top_type_share = (result_types.most_common(1)[0][1] / n) if n and result_types else 1.0
    domain_diversity = len(unique_domains) / n if n else 0.0
    exact_title_share = exact_title_count / n if n else 0.0
    platform_share = platform_count / n if n else 0.0
    shopping_present = "shopping" in present_features
    urls = [normalize_url(clean_text(row.get("url"))) for row in organic]
    urls = [url for url in urls if url]

    score: float | None = None
    priority = "Unscored"
    components: dict[str, float] = {}
    if n >= 3:
        components = {
            "base": 35.0,
            "domain_diversity": 25.0 * domain_diversity,
            "low_exact_title_saturation": 15.0 * (1.0 - exact_title_share),
            "result_format_opening": 10.0 * (1.0 - top_type_share),
            "paa_evidence": 5.0 if paa else 0.0,
            "ugc_opening": 5.0 if 1 <= forum_count <= 3 else 0.0,
            "platform_concentration_penalty": -20.0 * platform_share,
            "shopping_saturation_penalty": -5.0 if shopping_present and platform_share >= 0.3 else 0.0,
        }
        score = round(min(100.0, max(0.0, sum(components.values()))), 1)
        priority = "P1" if score >= 70 else ("P2" if score >= 50 else "P3")

    intent, intent_basis = infer_intent(query, present_features, result_types)
    content_type, angle = content_recommendation(intent, result_types, paa, query)
    domain_counts = Counter(domains)
    top_domains = [domain for domain, _ in domain_counts.most_common(5)]
    evidence = (
        f"{len(unique_domains)} unique domains/{n} organic; "
        f"{platform_share:.0%} platform share; {len(paa)} PAA; {exact_title_share:.0%} exact-title saturation"
    )
    return {
        "keyword": query,
        "seed_or_parent": clean_text(entry.get("parent_query")) or query,
        "parent_query": clean_text(entry.get("parent_query")),
        "discovery_source": clean_text(entry.get("discovery_source")) or "seed",
        "expansion_depth": entry.get("expansion_depth", 0),
        "data_status": "observed" if n >= 3 else "insufficient_serp",
        "serp_opportunity_score": score,
        "serp_priority": priority,
        "intent": intent,
        "intent_basis": intent_basis,
        "recommended_content_type": content_type,
        "recommended_angle": angle,
        "organic_result_count": n,
        "unique_domain_count": len(unique_domains),
        "domain_diversity": round(domain_diversity, 3),
        "exact_title_count": exact_title_count,
        "exact_title_share": round(exact_title_share, 3),
        "platform_count": platform_count,
        "platform_share": round(platform_share, 3),
        "forum_count": forum_count,
        "paa_count": len(paa),
        "related_search_count": len(entry.get("related_searches") or []),
        "serp_features": sorted(present_features),
        "dominant_result_type": result_types.most_common(1)[0][0] if result_types else "unknown",
        "top_domains": top_domains,
        "evidence": evidence,
        "score_components": {key: round(value, 2) for key, value in components.items()},
        "normalized_urls": urls,
        "provider": clean_text(entry.get("provider")),
        "country": clean_text(entry.get("country")),
        "language": clean_text(entry.get("language")),
        "location": clean_text(entry.get("location")),
        "device": clean_text(entry.get("device")),
        "retrieved_at": clean_text(entry.get("retrieved_at")),
        "cluster_id": "",
    }


class UnionFind:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))

    def find(self, value: int) -> int:
        while self.parent[value] != value:
            self.parent[value] = self.parent[self.parent[value]]
            value = self.parent[value]
        return value

    def union(self, left: int, right: int) -> None:
        root_left, root_right = self.find(left), self.find(right)
        if root_left != root_right:
            self.parent[root_right] = root_left


def assign_clusters(observed: list[dict[str, Any]], discovered: list[dict[str, Any]]) -> list[dict[str, Any]]:
    union = UnionFind(len(observed))
    url_sets = [set(item.get("normalized_urls") or []) for item in observed]
    for left in range(len(observed)):
        for right in range(left + 1, len(observed)):
            overlap = len(url_sets[left] & url_sets[right])
            denominator = min(len(url_sets[left]), len(url_sets[right]))
            coefficient = overlap / denominator if denominator else 0.0
            if overlap >= 3 or coefficient >= 0.35:
                union.union(left, right)

    groups: dict[int, list[int]] = defaultdict(list)
    for index in range(len(observed)):
        groups[union.find(index)].append(index)
    ordered_groups = sorted(groups.values(), key=lambda members: min(members))
    clusters: list[dict[str, Any]] = []
    query_to_cluster: dict[str, str] = {}
    for number, members in enumerate(ordered_groups, 1):
        cluster_id = f"C{number:02d}"
        ranked = sorted(
            (observed[index] for index in members),
            key=lambda row: (row.get("serp_opportunity_score") is not None, row.get("serp_opportunity_score") or -1),
            reverse=True,
        )
        representative = ranked[0]["keyword"]
        scores = [row["serp_opportunity_score"] for row in ranked if row.get("serp_opportunity_score") is not None]
        domain_counter: Counter[str] = Counter()
        for index in members:
            observed[index]["cluster_id"] = cluster_id
            query_to_cluster[key_text(observed[index]["keyword"])] = cluster_id
            domain_counter.update(observed[index].get("top_domains") or [])
        clusters.append({
            "cluster_id": cluster_id,
            "representative_keyword": representative,
            "fetched_query_count": len(members),
            "discovered_only_count": 0,
            "member_count": len(members),
            "average_serp_score": round(sum(scores) / len(scores), 1) if scores else None,
            "member_keywords": [row["keyword"] for row in ranked],
            "common_domains": [domain for domain, count in domain_counter.most_common(5) if count >= 2],
        })

    cluster_lookup = {cluster["cluster_id"]: cluster for cluster in clusters}
    for item in discovered:
        parent_key = key_text(item.get("parent_query") or item.get("seed_or_parent") or "")
        cluster_id = query_to_cluster.get(parent_key)
        if not cluster_id and clusters:
            cluster_id = clusters[0]["cluster_id"]
        item["cluster_id"] = cluster_id or ""
        if cluster_id:
            cluster = cluster_lookup[cluster_id]
            cluster["discovered_only_count"] += 1
            cluster["member_count"] += 1
            cluster["member_keywords"].append(item["keyword"])
    return clusters


def discovered_candidates(entries: list[dict[str, Any]], observed_keys: set[str]) -> list[dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for entry in entries:
        parent = clean_text(entry.get("query"))
        base = {
            "seed_or_parent": clean_text(entry.get("parent_query")) or parent,
            "parent_query": parent,
            "expansion_depth": int(entry.get("expansion_depth") or 0) + 1,
            "provider": clean_text(entry.get("provider")),
            "country": clean_text(entry.get("country")),
            "language": clean_text(entry.get("language")),
            "location": clean_text(entry.get("location")),
            "device": clean_text(entry.get("device")),
            "retrieved_at": clean_text(entry.get("retrieved_at")),
        }
        sources = [
            ("related_search", clean_text(item.get("query")))
            for item in (entry.get("related_searches") or []) if isinstance(item, dict)
        ] + [
            ("people_also_ask", clean_text(item.get("question")))
            for item in (entry.get("people_also_ask") or []) if isinstance(item, dict)
        ]
        for source, keyword in sources:
            key = key_text(keyword)
            if not key or key in observed_keys or key in found:
                continue
            found[key] = {
                "keyword": keyword,
                **base,
                "discovery_source": source,
                "data_status": "discovered_only",
                "serp_opportunity_score": None,
                "serp_priority": "Unscored",
                "intent": "unscored",
                "intent_basis": "own SERP not fetched",
                "recommended_content_type": "requires SERP fetch",
                "recommended_angle": "Fetch this query's SERP before choosing an angle.",
                "organic_result_count": 0,
                "unique_domain_count": 0,
                "domain_diversity": None,
                "exact_title_count": 0,
                "exact_title_share": None,
                "platform_count": 0,
                "platform_share": None,
                "forum_count": 0,
                "paa_count": 0,
                "related_search_count": 0,
                "serp_features": [],
                "dominant_result_type": "unknown",
                "top_domains": [],
                "evidence": "Discovered from parent SERP; own SERP not fetched.",
                "score_components": {},
                "normalized_urls": [],
                "cluster_id": "",
            }
    return list(found.values())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_path = Path(args.input).expanduser().resolve()
    source = json.loads(source_path.read_text(encoding="utf-8"))
    if source.get("schema_version") != "1.0" or not isinstance(source.get("queries"), list):
        raise SystemExit("Unsupported normalized SERP schema")
    entries = [entry for entry in source["queries"] if isinstance(entry, dict) and entry.get("status") == "ok"]
    if not entries:
        raise SystemExit("No successful SERP queries are available for analysis")

    observed = [analyze_query(entry) for entry in entries]
    observed_keys = {key_text(row["keyword"]) for row in observed}
    discovered = discovered_candidates(entries, observed_keys)
    clusters = assign_clusters(observed, discovered)
    opportunities = observed + discovered
    opportunities.sort(
        key=lambda row: (
            row.get("serp_opportunity_score") is not None,
            row.get("serp_opportunity_score") if row.get("serp_opportunity_score") is not None else -1,
            row["keyword"].casefold(),
        ),
        reverse=True,
    )

    organic_rows: list[dict[str, Any]] = []
    discovery_rows: list[dict[str, Any]] = []
    provenance: list[dict[str, Any]] = []
    all_domains: set[str] = set()
    present_feature_count = 0
    for entry in entries:
        query = clean_text(entry.get("query"))
        for result in entry.get("organic_results") or []:
            if not isinstance(result, dict):
                continue
            domain = domain_of(result.get("url", ""), result.get("domain", ""))
            if domain:
                all_domains.add(domain)
            organic_rows.append({
                "query": query,
                "position": result.get("position"),
                "rank_absolute": result.get("rank_absolute"),
                "title": clean_text(result.get("title")),
                "domain": domain,
                "url": clean_text(result.get("url")),
                "normalized_url": normalize_url(clean_text(result.get("url"))),
                "snippet": clean_text(result.get("snippet")),
                "result_type": clean_text(result.get("result_type")) or "organic",
            })
        for item in entry.get("people_also_ask") or []:
            if isinstance(item, dict) and clean_text(item.get("question")):
                discovery_rows.append({"parent_query": query, "source_type": "people_also_ask", "discovered_query": clean_text(item.get("question")), "evidence_url": clean_text(item.get("url")), "snippet": clean_text(item.get("snippet"))})
        for item in entry.get("related_searches") or []:
            if isinstance(item, dict) and clean_text(item.get("query")):
                discovery_rows.append({"parent_query": query, "source_type": "related_search", "discovered_query": clean_text(item.get("query")), "evidence_url": "", "snippet": ""})
        features = entry.get("features") or {}
        present = [name for name, value in features.items() if isinstance(value, dict) and value.get("present")]
        unavailable = [name for name, value in features.items() if isinstance(value, dict) and not value.get("available")]
        present_feature_count += len(present)
        provenance.append({
            "query": query,
            "provider": clean_text(entry.get("provider")),
            "country": clean_text(entry.get("country")),
            "language": clean_text(entry.get("language")),
            "location": clean_text(entry.get("location")),
            "device": clean_text(entry.get("device")),
            "retrieved_at": clean_text(entry.get("retrieved_at")),
            "status": clean_text(entry.get("status")),
            "organic_result_count": len(entry.get("organic_results") or []),
            "features_present": ", ".join(sorted(present)),
            "features_unavailable": ", ".join(sorted(unavailable)),
            "diagnostic": "",
        })
    for failed in source.get("failed_queries") or []:
        if isinstance(failed, dict):
            provenance.append({
                "query": clean_text(failed.get("query")), "provider": clean_text(source.get("meta", {}).get("provider")),
                "country": clean_text(source.get("meta", {}).get("country")), "language": clean_text(source.get("meta", {}).get("language")),
                "location": clean_text(source.get("meta", {}).get("location")), "device": clean_text(source.get("meta", {}).get("device")),
                "retrieved_at": "", "status": "error", "organic_result_count": 0, "features_present": "",
                "features_unavailable": "", "diagnostic": clean_text(failed.get("diagnostic")),
            })

    priority_counts = Counter(row["serp_priority"] for row in opportunities)
    scored_count = sum(row.get("serp_opportunity_score") is not None for row in opportunities)
    caveats = [
        "SERP-only analysis: no search volume, CPC, keyword difficulty, traffic, conversion, backlink, or business-fit data is used.",
        "serp_opportunity_score is a transparent heuristic for visible SERP attainability and format opening, not total SEO opportunity.",
        "SERPs are time-, location-, language-, and device-specific snapshots and can change after retrieval.",
    ]
    if source.get("meta", {}).get("partial"):
        caveats.append("The run is partial because one or more queries failed; inspect Provenance before decisions.")
    if discovered:
        caveats.append("Discovered-only PAA/related queries are unscored until their own SERP is fetched.")

    output = {
        "schema_version": "1.0",
        "meta": {
            **(source.get("meta") or {}),
            "analysis_generated_at": utc_now(),
            "source_file": source_path.name,
            "observed_query_count": len(observed),
            "discovered_only_count": len(discovered),
            "opportunity_count": len(opportunities),
            "scored_query_count": scored_count,
            "organic_result_count": len(organic_rows),
            "unique_domain_count": len(all_domains),
            "present_feature_count": present_feature_count,
            "cluster_count": len(clusters),
            "priority_counts": {key: priority_counts.get(key, 0) for key in ("P1", "P2", "P3", "Unscored")},
        },
        "caveats": caveats,
        "opportunities": opportunities,
        "clusters": clusters,
        "organic_results": organic_rows,
        "paa_and_related": discovery_rows,
        "provenance": provenance,
        "methodology": {
            "score_name": "serp_opportunity_score",
            "score_scope": "Visible SERP attainability and format opening only",
            "cluster_method": "Top-10 normalized URL overlap: >=3 shared URLs or overlap coefficient >=0.35",
            "priority_thresholds": "P1 >=70; P2 50–69.9; P3 <50; Unscored when own SERP is missing or insufficient",
        },
    }
    output_path = Path(args.output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output_path), "observed": len(observed), "discovered_only": len(discovered), "clusters": len(clusters)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
