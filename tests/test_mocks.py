"""The reconciliation finds what it should: every build 1.0 defect in mock 1,
only DEF-BPM-007 in mock 2, and a completeness bridge that always balances."""

from __future__ import annotations

import pytest

MOCK1_FAILED = {"RC-L1-02", "RC-L1-04", "RC-L1-05", "RC-L2-03", "RC-L2-04", "RC-L2-05", "RC-L2-06", "RC-L2-07",
                "RC-L2-08", "RC-L2-09", "RC-L2-10", "RC-L3-02", "RC-L3-03", "RC-L3-05", "RC-RI-09", "RC-RI-10",
                "RC-L4-01", "RC-L4-02", "RC-L4-03", "RC-L4-04", "RC-L4-05"}
MOCK2_FAILED = {"RC-L2-09", "RC-L3-05", "RC-RI-11", "RC-L4-05"}


def test_check_counts(mock1, mock2):
    # RC-RI-11 was added after mock 1 (DEC-BPM-011)
    assert len(mock1.checks) == 36 and "RC-RI-11" not in mock1.checks
    assert len(mock2.checks) == 37


def test_mock1_results(mock1):
    assert mock1.summary["checks_passed"] == 13
    assert set(mock1.summary["checks_failed"]) == MOCK1_FAILED
    assert set(mock1.summary["checks_no_data"]) == {"RC-L3-04", "RC-RI-04"}


def test_mock2_results(mock2):
    assert mock2.summary["checks_passed"] == 33
    assert set(mock2.summary["checks_failed"]) == MOCK2_FAILED
    assert mock2.summary["checks_no_data"] == []


def test_a_check_that_compared_nothing_is_not_a_pass(mock1):
    for check_id in ("RC-L3-04", "RC-RI-04"):
        assert mock1.checks[check_id]["compared"] == "0"
        assert mock1.result(check_id) == "NO DATA"


@pytest.mark.parametrize("defect, evidence", [
    ("DEF-BPM-001", {"invoices.invoice_date": 197}),
    ("DEF-BPM-002", {"subscriptions.status": 105}),
    ("DEF-BPM-003", {"payments.currency": 7176}),
    ("DEF-BPM-004", {"invoices.subscription": 419}),
    ("DEF-BPM-005", {"invoices.tax": 1192, "invoices.total": 1267, "invoices.amount_due": 49}),
])
def test_each_mock1_defect_shows_in_field_level(mock1, defect, evidence):
    for field, n in evidence.items():
        assert mock1.fields[field] == n, f"{defect}: {field}"


def test_mock1_field_level_has_nothing_else(mock1):
    expected = {"invoices.invoice_date", "subscriptions.status", "payments.currency", "invoices.subscription",
                "invoices.tax", "invoices.total", "invoices.amount_due"}
    assert {k for k, v in mock1.fields.items() if v} == expected


def test_mock1_completeness_evidence(mock1):
    # DEF-BPM-004: merged-away customers' subscriptions missing
    assert mock1.bridge["subscriptions"]["missing_in_target"] == 24
    # DEF-BPM-006: credit notes loaded into the invoice table
    assert mock1.bridge["credit notes"]["missing_in_target"] == 444
    assert mock1.bridge["invoices"]["not_expected"] == 444
    assert mock1.failures("RC-RI-09") == 7170
    assert mock1.failures("RC-RI-10") == 444 + 1163


def test_each_run_reports_only_its_own_field_coverage(mock1):
    # mock 1 ran without payment date in coverage (DEC-BPM-011 added it), so its results have no paid_date line
    assert "payments.paid_date" not in mock1.fields


def test_mock2_only_defect_is_payment_dates(mock2):
    assert {k for k, v in mock2.fields.items() if v} == {"payments.paid_date"}
    assert mock2.fields["payments.paid_date"] == 1463
    assert mock2.failures("RC-L2-09") == 139
    assert mock2.failures("RC-RI-11") == 34


@pytest.mark.parametrize("run_id", ["mock1", "mock2"])
def test_l1_bridge_balances(runs, run_id):
    for entity, b in runs[run_id].bridge.items():
        assert b["source_rows"] == b["merged"] + b["out_of_scope"] + b["expected_rejects"] + b["expected_loads"], entity
        assert b["bridge_balances"] == 1 and b["loaded_twice"] == 0, entity


def test_accepted_exceptions(mock2):
    assert mock2.summary["accepted_exceptions"] == {"EX-01": 23, "EX-02": 80, "EX-03": 25, "EX-04": 6}


def test_a_record_loaded_twice_fails_l1(runs, tmp_path):
    """Load one invoice and one customer a second time, under new platform ids, the way a
    re-run load step would: L1 must fail on both."""
    import json
    import shutil

    from conftest import ROOT
    from recon import engine

    src = runs["mock2"].folder.parent / "target" / "mock2"
    dst = tmp_path / "target"
    shutil.copytree(src, dst)
    for name, new_id in (("invoices.csv", "in_9999999"), ("customers.csv", "cus_999999")):
        lines = (dst / name).read_text(encoding="utf-8").splitlines(keepends=True)
        again = new_id + lines[1][lines[1].index(","):]
        (dst / name).write_text("".join(lines + [again]), encoding="utf-8")
    cfg = json.loads((ROOT / "config" / "mock2.json").read_text(encoding="utf-8"))
    summary = engine.reconcile(cfg, dst, tmp_path / "out")
    assert {"RC-L1-01", "RC-L1-04"} <= set(summary["checks_failed"])
    assert summary["l1_bridge"]["invoices"]["loaded_twice"] == 1
    assert summary["l1_bridge"]["customers"]["loaded_twice"] == 1


def test_mock2_loads_everything_expected(mock2):
    for entity, b in mock2.bridge.items():
        assert b["actual_loads"] == b["expected_loads"], entity
        assert b["missing_in_target"] == 0 and b["not_expected"] == 0, entity
    assert sum(b["actual_loads"] for b in mock2.bridge.values()) == 50069


def test_mock2_receivables_match(mock2):
    money = mock2.summary["money"]
    assert money["expected_open_ar_by_currency"] == money["actual_open_ar_by_currency"]
    assert money["expected_open_ar_by_currency"] == {"CAD": "331093.70", "EUR": "43081.77", "GBP": "99317.02",
                                                     "USD": "228757.51"}
