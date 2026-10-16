"""Reconciliation workbook for one mock run (the file Finance actually opens).

Sheets: Summary, L1 Completeness, L2 Control totals, L3 Fields, L3 Differences,
Integrity, L4 Finance, Source DQ.
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

NAVY = "1F3A5F"
PASS_FILL = PatternFill("solid", fgColor="E2F0D9")
FAIL_FILL = PatternFill("solid", fgColor="F8D7DA")
NODATA_FILL = PatternFill("solid", fgColor="FFF2CC")
HEAD_FILL = PatternFill("solid", fgColor=NAVY)
BAND_FILL = PatternFill("solid", fgColor="F3F5F8")
HEAD_FONT = Font(bold=True, color="FFFFFF")
THIN = Side(style="thin", color="C9CED6")
BOX = Border(top=THIN, bottom=THIN, left=THIN, right=THIN)

LEVEL_NAMES = {"L1": "L1 Completeness", "L2": "L2 Control totals", "L3": "L3 Field level",
               "RI": "Referential integrity", "L4": "L4 Finance views"}


def freeze_xlsx(path: Path, when: datetime) -> None:
    """Make a saved workbook byte-identical on every run: openpyxl stamps the
    save time into docProps/core.xml and into each zip entry. Both are set to
    `when` instead, so re-running a mock doesn't show the workbook as changed."""
    import re
    import zipfile

    stamp = when.strftime("%Y-%m-%dT%H:%M:%SZ")
    with zipfile.ZipFile(path) as z:
        entries = [(info, z.read(info.filename)) for info in z.infolist()]
    tmp = path.with_suffix(".tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for info, data in entries:
            if info.filename == "docProps/core.xml":
                data = re.sub(rb"(<dcterms:(created|modified)[^>]*>)[^<]*", lambda m: m.group(1) + stamp.encode(), data)
            fixed = zipfile.ZipInfo(info.filename, date_time=when.timetuple()[:6])
            fixed.compress_type = zipfile.ZIP_DEFLATED
            fixed.external_attr = info.external_attr
            z.writestr(fixed, data)
    tmp.replace(path)


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _num(v):
    if v is None or v == "":
        return v
    try:
        return int(v)
    except ValueError:
        try:
            return float(v)
        except ValueError:
            return v


def _table(ws, top: int, rows: list[dict], columns: list[tuple[str, str, int]], result_col: str | None = None,
           money_cols: tuple[str, ...] = (), max_rows: int | None = None) -> int:
    """Write a header and rows starting at row `top`. Returns the next free row."""
    for j, (_, label, width) in enumerate(columns, start=1):
        c = ws.cell(row=top, column=j, value=label)
        c.font, c.fill, c.alignment, c.border = HEAD_FONT, HEAD_FILL, Alignment(vertical="center", wrap_text=True), BOX
        if ws.column_dimensions[get_column_letter(j)].width in (None, 13):
            ws.column_dimensions[get_column_letter(j)].width = width
        ws.column_dimensions[get_column_letter(j)].width = max(ws.column_dimensions[get_column_letter(j)].width or 0, width)
    shown = rows if max_rows is None else rows[:max_rows]
    for i, row in enumerate(shown, start=top + 1):
        for j, (key, _, _) in enumerate(columns, start=1):
            v = row.get(key)
            c = ws.cell(row=i, column=j, value=_num(v) if key not in ("legacy_key", "dimension", "record_key") else v)
            c.border = BOX
            if key in money_cols and isinstance(c.value, (int, float)):
                c.number_format = "#,##0.00"
            elif isinstance(c.value, int):
                c.number_format = "#,##0"
            if (i - top) % 2 == 0:
                c.fill = BAND_FILL
        if result_col:
            res = row.get(result_col)
            fill = (PASS_FILL if res in ("PASS", "0", 0) else NODATA_FILL if res == "NO DATA"
                    else FAIL_FILL if res else None)
            if fill:
                for j in range(1, len(columns) + 1):
                    ws.cell(row=i, column=j).fill = fill
    end = top + len(shown)
    if rows:
        ws.auto_filter.ref = f"A{top}:{get_column_letter(len(columns))}{end}"
    if max_rows is not None and len(rows) > max_rows:
        ws.cell(row=end + 1, column=1, value=f"First {max_rows:,} of {len(rows):,} rows shown. The full list is in the CSV next to this workbook.").font = Font(italic=True)
        end += 1
    return end + 2


def _title(ws, text: str, sub: str | None = None) -> int:
    ws["A1"] = text
    ws["A1"].font = Font(bold=True, size=14, color=NAVY)
    if sub:
        ws["A2"] = sub
        ws["A2"].font = Font(italic=True, color="555555")
    return 4


def build(out: Path, summary: dict) -> Path:
    checks = _read(out / "checks.csv")
    wb = Workbook()

    # ---- Summary --------------------------------------------------------------
    ws = wb.active
    ws.title = "Summary"
    ws.sheet_view.showGridLines = False
    _title(ws, f"Northstar billing migration: {summary['label']} reconciliation",
           "Fictional client. Generated from the run outputs in this folder; do not edit by hand.")
    facts = [("Run", summary["label"]), ("Run date", summary["run_date"]),
             ("Migration build", summary["migration_build"]), ("Legacy extract as of", "2026-09-30"),
             ("Checks passed", f"{summary['checks_passed']} of {summary['checks_total']}"),
             ("Checks failed", ", ".join(summary["checks_failed"]) or "none"),
             ("No data to compare", ", ".join(summary.get("checks_no_data", [])) or "none")]
    for i, (k, v) in enumerate(facts, start=4):
        ws.cell(row=i, column=1, value=k).font = Font(bold=True)
        ws.cell(row=i, column=2, value=v)
    ws.column_dimensions["A"].width = 24
    ws.column_dimensions["B"].width = 16

    lvl_top = 4 + len(facts) + 2
    ws.cell(row=lvl_top - 1, column=1, value="By level").font = Font(bold=True, color=NAVY)
    lvl_rows = [{"level": LEVEL_NAMES[k], "total": v["total"], "passed": v["passed"], "failed": v["total"] - v["passed"]}
                for k, v in summary["by_level"].items()]
    nxt = _table(ws, lvl_top, lvl_rows, [("level", "Level", 24), ("total", "Checks", 10), ("passed", "Passed", 10),
                                          ("failed", "Not passed", 11)])
    chart = BarChart()
    chart.type, chart.grouping, chart.overlap = "bar", "stacked", 100
    chart.title, chart.height, chart.width = "Checks by level", 6.5, 12
    data = Reference(ws, min_col=3, min_row=lvl_top, max_col=4, max_row=lvl_top + len(lvl_rows))
    cats = Reference(ws, min_col=1, min_row=lvl_top + 1, max_row=lvl_top + len(lvl_rows))
    chart.add_data(data, titles_from_data=True)
    chart.set_categories(cats)
    chart.series[0].graphicalProperties.solidFill = "6AA84F"
    chart.series[1].graphicalProperties.solidFill = "CC4125"
    chart.y_axis.majorGridlines = None
    ws.add_chart(chart, "G4")

    nxt += 1
    ws.cell(row=nxt - 1, column=1, value="All checks").font = Font(bold=True, color=NAVY)
    _table(ws, nxt, checks, [("check_id", "Check", 12), ("level", "Level", 7), ("entity", "Entity", 14),
                             ("title", "What it proves", 56), ("compared", "Compared", 12),
                             ("failures", "Differences", 12), ("result", "Result", 9)], result_col="result")
    ws.freeze_panes = "A4"

    # ---- L1 ----------------------------------------------------------------------
    ws = wb.create_sheet("L1 Completeness")
    top = _title(ws, "Level 1: completeness bridge",
                 "Source rows = merged + out of scope + expected rejects + expected loads. Then expected loads against actual loads, key by key.")
    nxt = _table(ws, top, _read(out / "l1_bridge.csv"),
                 [("entity", "Entity", 14), ("source_rows", "Legacy rows", 12), ("merged", "Merged duplicates", 12),
                  ("out_of_scope", "Out of scope", 12), ("expected_rejects", "Expected rejects", 12),
                  ("expected_loads", "Expected loads", 12), ("actual_loads", "Actual loads", 12),
                  ("actual_rejects", "Actual rejects", 12), ("missing_in_target", "Missing in target", 12),
                  ("not_expected", "In target, not expected", 14)])
    _table(ws, nxt, _read(out / "l1_key_differences.csv"),
           [("check_id", "Check", 12), ("entity", "Entity", 14), ("legacy_key", "Legacy key", 14), ("issue", "Issue", 30)],
           max_rows=5000)

    # ---- L2 ----------------------------------------------------------------------
    ws = wb.create_sheet("L2 Control totals")
    top = _title(ws, "Level 2: control totals", "Tolerance is zero. Money in the record currency.")
    rows = _read(out / "l2_control_totals.csv")
    rows.sort(key=lambda r: (r["diff"] in ("0", "0.00"), r["check_id"], r["dimension"]))
    _table(ws, top, rows, [("check_id", "Check", 12), ("dimension", "Cut", 26), ("measure", "Measure", 20),
                           ("expected", "Expected", 16), ("actual", "Actual", 16), ("diff", "Difference", 14)],
           money_cols=("expected", "actual", "diff"))
    for r in range(top + 1, top + 1 + len(rows)):
        d = ws.cell(row=r, column=6).value
        fill = PASS_FILL if d in (0, 0.0) else FAIL_FILL
        for j in range(1, 7):
            ws.cell(row=r, column=j).fill = fill
    ws.freeze_panes = ws.cell(row=top + 1, column=1)

    # ---- L3 ----------------------------------------------------------------------
    ws = wb.create_sheet("L3 Fields")
    top = _title(ws, "Level 3: field-level comparison by field", summary.get("coverage_change") or None)
    _table(ws, top, _read(out / "l3_field_summary.csv"),
           [("check_id", "Check", 12), ("entity", "Entity", 14), ("field", "Field", 20),
            ("records_compared", "Records compared", 16), ("mismatches", "Mismatches", 12)], result_col="mismatches")

    ws = wb.create_sheet("L3 Differences")
    top = _title(ws, "Level 3: every field difference", "Expected is built from the legacy extract and the mapping rules; actual is the load file.")
    _table(ws, top, _read(out / "l3_field_differences.csv"),
           [("check_id", "Check", 12), ("entity", "Entity", 14), ("legacy_key", "Legacy key", 14),
            ("field", "Field", 16), ("expected", "Expected", 22), ("actual", "Actual", 22)], max_rows=10000)
    ws.freeze_panes = ws.cell(row=top + 1, column=1)

    # ---- Integrity ---------------------------------------------------------------------
    ws = wb.create_sheet("Integrity")
    top = _title(ws, "Referential integrity and internal consistency in the target")
    _table(ws, top, _read(out / "integrity_issues.csv"),
           [("check_id", "Check", 12), ("entity", "Entity", 14), ("target_key", "Target key", 14),
            ("legacy_key", "Legacy key", 14), ("issue", "Issue", 44)], max_rows=10000)

    # ---- L4 ---------------------------------------------------------------------------
    ws = wb.create_sheet("L4 Finance")
    top = _title(ws, "Level 4: receivables, aging, customer balances, September close")
    rows = _read(out / "l4_finance.csv")
    rows.sort(key=lambda r: (r["diff"] in ("0", "0.00"), r["check_id"], r["dimension"]))
    _table(ws, top, rows, [("check_id", "Check", 12), ("dimension", "Cut", 28), ("measure", "Measure", 16),
                           ("expected", "Expected", 16), ("actual", "Actual", 16), ("diff", "Difference", 14)],
           money_cols=("expected", "actual", "diff"))
    for r in range(top + 1, top + 1 + len(rows)):
        d = ws.cell(row=r, column=6).value
        for j in range(1, 7):
            ws.cell(row=r, column=j).fill = PASS_FILL if d in (0, 0.0) else FAIL_FILL

    # ---- Accepted exceptions -----------------------------------------------------------
    ws = wb.create_sheet("Accepted exceptions")
    top = _title(ws, "Accepted exceptions carried into the target",
                 "Built into the expected target, so they never show as differences. Register and approvals: docs/08.")
    _table(ws, top, _read(out / "accepted_exceptions.csv"),
           [("exception_id", "Exception", 11), ("entity", "Entity", 14), ("legacy_key", "Legacy key", 14),
            ("detail", "Detail", 60)])

    # ---- Source DQ ---------------------------------------------------------------------
    ws = wb.create_sheet("Source DQ")
    top = _title(ws, "Data quality rules on the legacy extract", "Handling for each rule: docs/04_data_quality_rules.md")
    dq = _read(out.parent / "profiling" / "dq_results.csv")
    _table(ws, top, dq, [("rule_id", "Rule", 9), ("title", "Rule", 46), ("source_table", "Table", 22),
                         ("severity", "Severity", 10), ("rows_checked", "Rows checked", 13), ("rows_failing", "Rows failing", 13)])

    for sheet in wb.worksheets:
        sheet.sheet_properties.tabColor = NAVY if sheet.title == "Summary" else "8EA9C1"
        sheet.page_setup.orientation = "landscape"
        sheet.sheet_properties.pageSetUpPr.fitToPage = True
        sheet.page_setup.fitToWidth = 1
        sheet.page_setup.fitToHeight = 0
    wb.properties.creator = "Northstar BPM data workstream"
    wb.properties.title = f"{summary['label']} reconciliation"
    wb.properties.created = datetime.strptime(summary["run_date"], "%Y-%m-%d").replace(hour=18)
    path = out / f"Northstar_BPM_Reconciliation_{summary['run_id'].capitalize()}.xlsx"
    wb.save(path)
    freeze_xlsx(path, wb.properties.created)
    return path
