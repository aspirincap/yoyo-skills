#!/usr/bin/env python3
"""Build a portable Excel workbook and offline HTML report from analysis JSON."""

from __future__ import annotations

import argparse
import html
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.table import Table, TableStyleInfo


FORBIDDEN_FIELDS = {"search_volume", "cpc", "keyword_difficulty", "kd", "traffic", "revenue"}
HEADER_FILL = PatternFill("solid", fgColor="1E3A5F")
HEADER_FONT = Font(name="Aptos", size=10, bold=True, color="FFFFFF")
BODY_FONT = Font(name="Aptos", size=10, color="172033")
LABEL_FILL = PatternFill("solid", fgColor="E8EEF7")


def text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(text(item) for item in value)
    return str(value)


def num(value: Any) -> float | int | None:
    if value in (None, ""):
        return None
    return value


def date_value(value: Any) -> datetime | str | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return text(value)


def escape(value: Any) -> str:
    return html.escape(text(value), quote=True)


def write_rows(sheet, headers: list[str], rows: list[list[Any]]) -> int:
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    for cell in sheet[1]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(vertical="top", wrap_text=True)
    for row in sheet.iter_rows(min_row=2):
        for cell in row:
            cell.font = BODY_FONT
            cell.alignment = Alignment(vertical="top", wrap_text=True)
    return len(rows) + 1


def style_table(sheet, end_row: int, end_col: int, widths: dict[str, int]) -> None:
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = f"A1:{sheet.cell(end_row, end_col).coordinate}"
    for column, width in widths.items():
        sheet.column_dimensions[column].width = width


def add_table(sheet, end_row: int, end_col: int, name: str) -> None:
    ref = f"A1:{sheet.cell(end_row, end_col).coordinate}"
    table = Table(displayName=name, ref=ref)
    table.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showFirstColumn=False, showLastColumn=False, showRowStripes=True, showColumnStripes=False)
    sheet.add_table(table)


def safe_text(value: Any) -> str:
    """Write provider text as a literal Excel string, never a formula."""
    value_text = text(value)
    # Excel treats cells beginning with these characters as formulas. Prefixing
    # an apostrophe keeps untrusted query/provider text literal while preserving
    # the displayed text in spreadsheet applications.
    if value_text[:1] in {"=", "+", "-", "@"}:
        return "'" + value_text
    return value_text


def validate_no_unexpected_formulas(workbook_path: Path) -> None:
    workbook = load_workbook(workbook_path, data_only=False, read_only=False)
    allowed = {f"E{row}" for row in range(4, 11)}
    for sheet in workbook.worksheets:
        for row in sheet.iter_rows():
            for cell in row:
                if cell.data_type == "f" and not (sheet.title == "Overview" and cell.coordinate in allowed):
                    raise RuntimeError(f"Unexpected formula in {sheet.title}!{cell.coordinate}")


def build_workbook(report: dict[str, Any], output_path: Path) -> None:
    workbook = Workbook()
    overview = workbook.active
    overview.title = "Overview"
    opportunities = workbook.create_sheet("Opportunities")
    clusters = workbook.create_sheet("Clusters")
    organic = workbook.create_sheet("Organic Results")
    discovery = workbook.create_sheet("PAA & Related")
    provenance = workbook.create_sheet("Provenance")
    meta = report.get("meta") or {}

    opp_headers = ["Keyword", "Cluster", "Discovery Source", "Data Status", "SERP Score", "SERP Priority", "Intent", "Recommended Content Type", "Recommended Angle", "Organic Results", "Unique Domains", "Domain Diversity", "Exact-title Share", "Platform Share", "Forum Results", "PAA Count", "Related Count", "Dominant Result Type", "Top Domains", "Evidence", "Parent Query", "Retrieved At"]
    opp_rows = [[safe_text(row.get("keyword")), safe_text(row.get("cluster_id")), safe_text(row.get("discovery_source")), safe_text(row.get("data_status")), num(row.get("serp_opportunity_score")), safe_text(row.get("serp_priority")), safe_text(row.get("intent")), safe_text(row.get("recommended_content_type")), safe_text(row.get("recommended_angle")), num(row.get("organic_result_count")), num(row.get("unique_domain_count")), num(row.get("domain_diversity")), num(row.get("exact_title_share")), num(row.get("platform_share")), num(row.get("forum_count")), num(row.get("paa_count")), num(row.get("related_search_count")), safe_text(row.get("dominant_result_type")), safe_text(row.get("top_domains")), safe_text(row.get("evidence")), safe_text(row.get("parent_query")), date_value(row.get("retrieved_at"))] for row in report["opportunities"]]
    opp_end = write_rows(opportunities, opp_headers, opp_rows)
    style_table(opportunities, opp_end, len(opp_headers), {"A": 30, "B": 10, "C": 18, "D": 18, "E": 12, "F": 13, "G": 15, "H": 26, "I": 48, "J": 13, "K": 13, "L": 15, "M": 15, "N": 14, "O": 13, "P": 10, "Q": 12, "R": 18, "S": 34, "T": 46, "U": 28, "V": 22})
    add_table(opportunities, opp_end, len(opp_headers), "OpportunitiesTable")
    for cell in opportunities["E"][1:]: cell.number_format = "0.0"
    for column in ("L", "M", "N"):
        for cell in opportunities[column][1:]: cell.number_format = "0.0%"

    cluster_headers = ["Cluster", "Representative Keyword", "Fetched Queries", "Discovered Only", "Members", "Average SERP Score", "Common Domains", "Member Keywords"]
    cluster_rows = [[safe_text(row.get("cluster_id")), safe_text(row.get("representative_keyword")), num(row.get("fetched_query_count")), num(row.get("discovered_only_count")), num(row.get("member_count")), num(row.get("average_serp_score")), safe_text(row.get("common_domains")), safe_text(row.get("member_keywords"))] for row in report.get("clusters", [])]
    cluster_end = write_rows(clusters, cluster_headers, cluster_rows or [["", "", None, None, None, None, "", ""]])
    style_table(clusters, cluster_end, len(cluster_headers), {"A": 10, "B": 32, "C": 15, "D": 16, "E": 10, "F": 18, "G": 36, "H": 60})
    if cluster_rows: add_table(clusters, cluster_end, len(cluster_headers), "ClustersTable")

    organic_headers = ["Query", "Position", "Absolute Rank", "Title", "Domain", "URL", "Normalized URL", "Snippet", "Result Type"]
    organic_rows = [[safe_text(row.get("query")), num(row.get("position")), num(row.get("rank_absolute")), safe_text(row.get("title")), safe_text(row.get("domain")), safe_text(row.get("url")), safe_text(row.get("normalized_url")), safe_text(row.get("snippet")), safe_text(row.get("result_type"))] for row in report.get("organic_results", [])]
    organic_end = write_rows(organic, organic_headers, organic_rows or [["", None, None, "", "", "", "", "", ""]])
    style_table(organic, organic_end, len(organic_headers), {"A": 30, "B": 10, "C": 13, "D": 45, "E": 28, "F": 56, "G": 56, "H": 60, "I": 16})
    if organic_rows: add_table(organic, organic_end, len(organic_headers), "OrganicResultsTable")

    discovery_headers = ["Parent Query", "Source Type", "Discovered Query", "Evidence URL", "Snippet"]
    discovery_rows = [[safe_text(row.get("parent_query")), safe_text(row.get("source_type")), safe_text(row.get("discovered_query")), safe_text(row.get("evidence_url")), safe_text(row.get("snippet"))] for row in report.get("paa_and_related", [])]
    discovery_end = write_rows(discovery, discovery_headers, discovery_rows or [["", "", "", "", ""]])
    style_table(discovery, discovery_end, len(discovery_headers), {"A": 32, "B": 20, "C": 50, "D": 55, "E": 60})
    if discovery_rows: add_table(discovery, discovery_end, len(discovery_headers), "DiscoveryTable")

    provenance_headers = ["Query", "Provider", "Country", "Language", "Location", "Device", "Retrieved At", "Status", "Organic Results", "Features Present", "Features Unavailable", "Diagnostic"]
    provenance_rows = [[safe_text(row.get("query")), safe_text(row.get("provider")), safe_text(row.get("country")), safe_text(row.get("language")), safe_text(row.get("location")), safe_text(row.get("device")), date_value(row.get("retrieved_at")), safe_text(row.get("status")), num(row.get("organic_result_count")), safe_text(row.get("features_present")), safe_text(row.get("features_unavailable")), safe_text(row.get("diagnostic"))] for row in report.get("provenance", [])]
    provenance_end = write_rows(provenance, provenance_headers, provenance_rows or [["", "", "", "", "", "", None, "", None, "", "", ""]])
    style_table(provenance, provenance_end, len(provenance_headers), {"A": 32, "B": 14, "C": 11, "D": 11, "E": 24, "F": 11, "G": 22, "H": 12, "I": 14, "J": 42, "K": 42, "L": 60})
    add_table(provenance, provenance_end, len(provenance_headers), "ProvenanceTable")

    overview.merge_cells("A1:H2")
    overview["A1"] = "SERP Keyword Research"
    overview["A1"].fill = PatternFill("solid", fgColor="163A63")
    overview["A1"].font = Font(name="Aptos Display", size=22, bold=True, color="FFFFFF")
    overview["A1"].alignment = Alignment(vertical="center")
    overview["A4"] = "Scope"; overview["B4"] = "SERP-only"
    overview["A5"] = "Provider"; overview["B5"] = safe_text(meta.get("provider"))
    overview["A6"] = "Country / Language"; overview["B6"] = f"{safe_text(meta.get('country'))} / {safe_text(meta.get('language'))}"
    overview["A7"] = "Device"; overview["B7"] = safe_text(meta.get("device"))
    overview["A8"] = "Generated"; overview["B8"] = date_value(meta.get("analysis_generated_at"))
    overview["A9"] = "Partial run"; overview["B9"] = "Yes" if meta.get("partial") else "No"
    overview["A10"] = "Seed queries"; overview["B10"] = safe_text(meta.get("seed_queries"))
    labels = ["Total opportunities", "Fetched/scored", "Discovered only", "P1", "P2", "P3", "Unscored"]
    for row, label in enumerate(labels, 4): overview.cell(row, 4).value = label
    overview["E4"] = f"=COUNTA('Opportunities'!$A$2:$A${opp_end})"
    overview["E5"] = f"=COUNT('Opportunities'!$E$2:$E${opp_end})"
    overview["E6"] = f'=COUNTIF(\'Opportunities\'!$D$2:$D${opp_end},"discovered_only")'
    overview["E7"] = f'=COUNTIF(\'Opportunities\'!$F$2:$F${opp_end},"P1")'
    overview["E8"] = f'=COUNTIF(\'Opportunities\'!$F$2:$F${opp_end},"P2")'
    overview["E9"] = f'=COUNTIF(\'Opportunities\'!$F$2:$F${opp_end},"P3")'
    overview["E10"] = f'=COUNTIF(\'Opportunities\'!$F$2:$F${opp_end},"Unscored")'
    for row in range(4, 11):
        overview.cell(row, 1).fill = LABEL_FILL; overview.cell(row, 1).font = Font(bold=True)
        overview.cell(row, 4).fill = LABEL_FILL; overview.cell(row, 4).font = Font(bold=True)
        overview.cell(row, 2).alignment = Alignment(wrap_text=True)
    overview.merge_cells("A12:H12"); overview["A12"] = "Important limitations"; overview["A12"].fill = PatternFill("solid", fgColor="FFF0CF")
    overview.merge_cells("A13:H13"); overview["A13"] = "\n".join(f"• {text(item)}" for item in report.get("caveats", [])); overview["A13"].alignment = Alignment(wrap_text=True, vertical="top")
    overview.merge_cells("A15:H15"); overview["A15"] = "Methodology"; overview["A15"].fill = PatternFill("solid", fgColor="DDE8F7")
    overview.merge_cells("A16:H19"); overview["A16"] = f"Score: {text(report.get('methodology', {}).get('score_scope'))}\nThresholds: {text(report.get('methodology', {}).get('priority_thresholds'))}\nClusters: {text(report.get('methodology', {}).get('cluster_method'))}\nThis workbook intentionally contains no search volume, CPC, KD, traffic, backlink, conversion, or revenue metrics."; overview["A16"].alignment = Alignment(wrap_text=True, vertical="top")
    overview.column_dimensions["A"].width = 24; overview.column_dimensions["B"].width = 38; overview.column_dimensions["D"].width = 24; overview.column_dimensions["E"].width = 14
    overview.freeze_panes = "A3"
    workbook.save(output_path)
    validate_no_unexpected_formulas(output_path)


def html_table(headers: list[str], rows: list[list[Any]]) -> str:
    head = "".join(f"<th>{escape(item)}</th>" for item in headers)
    body = "".join("<tr>" + "".join(f"<td>{escape(item)}</td>" for item in row) + "</tr>" for row in rows)
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body or '<tr><td colspan="' + str(len(headers)) + '">No data</td></tr>'}</tbody></table>"


def build_html(report: dict[str, Any], template_path: Path, output_path: Path, workbook_name: str) -> None:
    meta = report.get("meta") or {}
    opportunities = [row for row in report.get("opportunities", []) if row.get("serp_opportunity_score") is not None][:20]
    top_rows = [[row.get("keyword"), f"{float(row['serp_opportunity_score']):.1f}", row.get("serp_priority"), row.get("intent"), row.get("evidence"), row.get("recommended_angle")] for row in opportunities]
    cards = "".join(f'<div class="card"><span>{escape(label)}</span><b>{escape(value)}</b></div>' for label, value in [("Fetched queries", meta.get("observed_query_count", 0)), ("Discovered only", meta.get("discovered_only_count", 0)), ("P1", (meta.get("priority_counts") or {}).get("P1", 0)), ("P2", (meta.get("priority_counts") or {}).get("P2", 0)), ("P3", (meta.get("priority_counts") or {}).get("P3", 0)), ("Clusters", meta.get("cluster_count", 0))])
    clusters = "".join(f'<article class="cluster"><h3>{escape(row.get("cluster_id"))} · {escape(row.get("representative_keyword"))}</h3><p>{escape(row.get("member_count"))} members · {escape(row.get("fetched_query_count"))} fetched · average score {escape(row.get("average_serp_score", "n/a"))}</p><p>{escape(" · ".join((row.get("member_keywords") or [])[:6]))}</p></article>' for row in report.get("clusters", [])) or "<p>No clusters available.</p>"
    discoveries = [[row.get("parent_query"), row.get("source_type"), row.get("discovered_query"), row.get("snippet") or row.get("evidence_url")] for row in (report.get("paa_and_related") or [])[:50]]
    limitations = "<strong>Do not read these scores as demand or KD.</strong><ul>" + "".join(f"<li>{escape(item)}</li>" for item in report.get("caveats", [])) + "</ul>"
    methodology = f'<p><b>Score:</b> {escape(report.get("methodology", {}).get("score_scope"))}</p><p><b>Priority:</b> {escape(report.get("methodology", {}).get("priority_thresholds"))}</p><p><b>Clusters:</b> {escape(report.get("methodology", {}).get("cluster_method"))}</p><p>Detailed ranked evidence is in <a href="./{escape(workbook_name)}">{escape(workbook_name)}</a>.</p>'
    values = {"TITLE": "SERP Keyword Research", "SUBTITLE": f"SERP-only analysis for {text(meta.get('seed_queries')) or 'seed queries'}.", "META": "".join(f"<span>{label}: <b>{escape(value)}</b></span>" for label, value in [("Provider", meta.get("provider")), ("Market", f"{meta.get('country')} / {meta.get('language')}"), ("Device", meta.get("device")), ("Generated", meta.get("analysis_generated_at")), ("Coverage", "partial" if meta.get("partial") else "complete")]), "KPI_CARDS": cards, "LIMITATIONS": limitations, "TOP_TABLE": html_table(["Keyword", "Score", "Priority", "Intent", "Evidence", "Recommended angle"], top_rows), "CLUSTERS": clusters, "DISCOVERIES": html_table(["Parent query", "Source", "Discovered query", "Evidence"], discoveries), "METHODOLOGY": methodology, "FOOTER": f"Generated from {escape(meta.get('provider'))} SERP snapshots. Workbook: {escape(workbook_name)}."}
    rendered = template_path.read_text(encoding="utf-8")
    for token, value in values.items(): rendered = rendered.replace("{{" + token + "}}", value)
    if "{{" in rendered: raise RuntimeError("Unresolved HTML template token")
    output_path.write_text(rendered, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--template", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--base-name", required=True)
    parser.add_argument("--preview-dir", type=Path)
    args = parser.parse_args()
    report = json.loads(args.input.read_text(encoding="utf-8"))
    if report.get("schema_version") != "1.0" or not report.get("opportunities"):
        raise SystemExit("Unsupported or empty analysis schema")
    for row in report["opportunities"]:
        forbidden = FORBIDDEN_FIELDS.intersection(row)
        if forbidden: raise SystemExit("Forbidden non-SERP field in analysis: " + ", ".join(sorted(forbidden)))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    base_name = re.sub(r"[^A-Za-z0-9._-]+", "_", args.base_name)
    xlsx = args.output_dir / f"{base_name}.xlsx"
    html_path = args.output_dir / f"{base_name}.html"
    build_workbook(report, xlsx)
    build_html(report, args.template, html_path, xlsx.name)
    if args.preview_dir:
        args.preview_dir.mkdir(parents=True, exist_ok=True)
        (args.preview_dir / "README.txt").write_text("Portable builder verified the workbook and HTML; PNG previews require a spreadsheet renderer.\n", encoding="utf-8")
    print(json.dumps({"xlsx": str(xlsx.resolve()), "html": str(html_path.resolve()), "previews": str(args.preview_dir.resolve()) if args.preview_dir else None, "opportunities": len(report["opportunities"]), "organic_results": len(report.get("organic_results", []))}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
