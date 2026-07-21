#!/usr/bin/env python3
"""Offline smoke tests for the SERP keyword skill."""
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SmokeTest(unittest.TestCase):
    def test_builder_escapes_and_blocks_formula_injection(self):
        analyze = load("analyze", ROOT / "scripts/analyze_serp.py")
        builder = load("builder", ROOT / "scripts/build_reports.py")
        fixture = {"schema_version": "1.0", "meta": {"provider": "fixture", "seed_queries": ["seed"]}, "queries": [
            {"query": "seed", "parent_query": None, "discovery_source": "seed", "expansion_depth": 0, "provider": "fixture", "retrieved_at": "2026-01-01T00:00:00Z", "country": "us", "language": "en", "device": "desktop", "status": "ok", "organic_results": [{"position": 1, "title": "Safe", "url": "https://example.test/a", "domain": "example.test", "snippet": "ok"}], "people_also_ask": [{"question": "<img src=x>", "snippet": "unsafe"}], "related_searches": [{"query": "=HYPERLINK(\"https://evil.test\",\"x\")"}], "features": {}, "raw_response": {}}
        ], "failed_queries": []}
        with tempfile.TemporaryDirectory() as td:
            td = Path(td); normalized = td / "normalized.json"; analysis = td / "analysis.json"; normalized.write_text(json.dumps(fixture))
            subprocess.run(["python3", str(ROOT / "scripts/analyze_serp.py"), "--input", str(normalized), "--output", str(analysis)], check=True)
            report = json.loads(analysis.read_text())
            xlsx = td / "report.xlsx"; html = td / "report.html"
            builder.build_workbook(report, xlsx); builder.build_html(report, ROOT / "assets/report-template.html", html, xlsx.name)
            wb = load_workbook(xlsx, data_only=False)
            self.assertEqual(wb["Opportunities"]["A3"].data_type, "s")
            self.assertTrue("HYPERLINK" in wb["Opportunities"]["A3"].value)
            self.assertNotIn("<img src=x>", html.read_text())

    def test_secret_redaction(self):
        fetch = load("fetch", ROOT / "scripts/fetch_serp.py")
        clean = fetch.strip_secrets({"error": "invalid super-secret"}, ("super-secret",))
        self.assertEqual(clean["error"], "invalid ***redacted***")


if __name__ == "__main__":
    unittest.main()
