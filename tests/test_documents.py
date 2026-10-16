"""The numbers quoted in the documents are the numbers in the results.

Each test reads a figure from the run and checks that the document states it,
formatted the way the document formats it."""

from __future__ import annotations

import re

import pytest

from conftest import ROOT, read_csv

DOCS = ROOT / "docs"


def doc(name: str) -> str:
    text = (ROOT / name).read_text(encoding="utf-8") if name == "README.md" else (DOCS / name).read_text(encoding="utf-8")
    return text


def n(value: int) -> str:
    return f"{value:,}"


def money(value: str) -> str:
    whole, cents = value.lstrip("-").split(".")
    return f"{'-' if value.startswith('-') else ''}{int(whole):,}.{cents}"


@pytest.mark.parametrize("name", ["README.md", "01_engagement_brief.md", "06_mock1_reconciliation_report.md",
                                  "08_mock2_reconciliation_report.md", "10_go_no_go_recommendation.md"])
def test_headline_results(name, mock1, mock2):
    text = doc(name)
    for run in (mock1, mock2):
        s = run.summary
        if f"{s['checks_passed']} of {s['checks_total']}" in text:
            continue
        if name == "06_mock1_reconciliation_report.md" and run is mock2:
            continue
        if name == "08_mock2_reconciliation_report.md" and run is mock1:
            continue
        raise AssertionError(f"{name} does not state {s['checks_passed']} of {s['checks_total']} for {s['label']}")


def test_dq_catalog_counts(profile_facts):
    text = doc("04_data_quality_rules.md")
    for rule, count in profile_facts["dq"].items():
        row = next(line for line in text.splitlines() if line.startswith(f"| {rule} |"))
        assert f"| {n(count)} |" in row, f"{rule}: expected {count}"


def test_profiling_report_counts(profile_facts):
    text = doc("02_data_profiling_report.md")
    for table, count in profile_facts["row_counts"].items():
        assert re.search(rf"\| {table} \| {n(count)} \|", text), table
    assert n(profile_facts["total_rows"]) in text
    for rule, count in profile_facts["dq"].items():
        if count:
            assert f"({rule}: {n(count)} " in text or rule in ("DQ-12",) and f"({rule}: {n(count)} rows)" in text, rule
    assert f"{profile_facts['invoices_dated_differently_in_utc']} invoices and {n(profile_facts['payments_dated_differently_in_utc'])} payments" in text


def test_bridge_tables(mock1, mock2):
    def row(text, entity):
        line = next(line for line in text.splitlines() if line.startswith(f"| {entity} |"))
        return [c.strip() for c in line.strip("|").split("|")]

    text = doc("06_mock1_reconciliation_report.md")
    for entity, b in mock1.bridge.items():
        cols = ["source_rows", "merged", "out_of_scope", "expected_rejects", "expected_loads", "actual_loads",
                "missing_in_target", "not_expected"]
        assert row(text, entity)[1:] == [n(b[c]) for c in cols], f"mock 1 bridge, {entity}"
    text = doc("08_mock2_reconciliation_report.md")
    for entity, b in mock2.bridge.items():
        cols = ["source_rows", "merged", "out_of_scope", "expected_rejects", "actual_loads", "missing_in_target",
                "not_expected"]
        assert row(text, entity)[1:] == [n(b[c]) for c in cols], f"mock 2 bridge, {entity}"


def test_receivables_and_cash_figures(mock1, mock2, runs):
    m2 = mock2.summary["money"]
    for name in ("README.md", "08_mock2_reconciliation_report.md"):
        text = doc(name)
        for ccy, value in m2["expected_open_ar_by_currency"].items():
            assert money(value) in text, f"{name}: open AR {ccy}"
    m1 = mock1.summary["money"]
    text = doc("06_mock1_reconciliation_report.md")
    for ccy, value in m1["actual_open_ar_by_currency"].items():
        assert money(value) in text, f"mock 1 loaded AR {ccy}"
    l4 = read_csv(runs["mock2"].folder / "l4_finance.csv")
    for name in ("README.md", "08_mock2_reconciliation_report.md"):
        text = doc(name)
        for r in (r for r in l4 if r["check_id"] == "RC-L4-04"):
            assert money(r["expected"]) in text, f"{name}: September billing {r['dimension']}"
    cash = {r["dimension"]: r for r in l4 if r["check_id"] == "RC-L4-05"}
    text = doc("08_mock2_reconciliation_report.md")
    for ccy, r in cash.items():
        assert f"| {ccy} | {money(r['expected'])} | {money(r['actual'])} |" in text, ccy


def test_defect_log_counts(mock1, mock2):
    text = doc("07_defect_log.md")
    f1, f2 = mock1.fields, mock2.fields
    expected = {
        "DEF-BPM-001": n(f1["invoices.invoice_date"]),
        "DEF-BPM-002": n(f1["subscriptions.status"]),
        "DEF-BPM-003": n(f1["payments.currency"]),
        "DEF-BPM-004": f"{mock1.bridge['subscriptions']['missing_in_target']} subscriptions, {f1['invoices.subscription']} invoices",
        "DEF-BPM-005": f"{n(f1['invoices.tax'])} tax, {n(f1['invoices.total'])} totals",
        "DEF-BPM-006": n(mock1.bridge["credit notes"]["missing_in_target"]),
        "DEF-BPM-007": n(f2["payments.paid_date"]),
    }
    for defect, count in expected.items():
        row = next(line for line in text.splitlines() if line.startswith(f"| {defect} |"))
        assert f"| {count} |" in row, defect


def test_no_template_leftovers():
    for path in [ROOT / "README.md", *sorted(DOCS.glob("*.md"))]:
        text = path.read_text(encoding="utf-8")
        for marker in ("TODO", "TBD", "[insert", "lorem"):
            assert marker.lower() not in text.lower(), f"{path.name}: {marker}"
