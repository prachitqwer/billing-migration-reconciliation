"""Reconciliation engine: loads the legacy extract and a set of load files into
SQLite, runs the SQL in recon/sql in order, and writes the results.

The engine never imports the loader. Expected values come only from the legacy
extract, the value maps and the rules in recon/sql/02_expected_target.sql.
"""

from __future__ import annotations

import csv
import json
import re
import sqlite3
import unicodedata
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SQL = ROOT / "recon" / "sql"
EXTRACT = ROOT / "data" / "legacy_extract"
MAPS = ROOT / "config" / "value_maps"
SETTINGS = json.loads((ROOT / "config" / "migration_settings.json").read_text(encoding="utf-8"))

EMAIL_OK = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")

LEGACY_TABLES = ["lb_customers", "lb_plans", "lb_subscriptions", "lb_invoices", "lb_payments"]
MAP_TABLES = {
    "map_country": "country_map", "map_customer_status": "customer_status_map",
    "map_sub_status": "subscription_status_map", "map_inv_status": "invoice_status_map",
    "map_plan": "plan_map", "map_method": "payment_method_map", "map_tax": "tax_rates",
}
TARGET_TABLES = ["customers", "subscriptions", "invoices", "credit_notes", "payments", "load_rejects"]
L3_CHECKS = [("RC-L3-01", "customers"), ("RC-L3-02", "subscriptions"), ("RC-L3-03", "invoices"),
             ("RC-L3-04", "credit_notes"), ("RC-L3-05", "payments")]


# ------------------------------------------------------------------ helpers

def _nfold(value):
    if value is None:
        return None
    folded = unicodedata.normalize("NFC", value).casefold().replace(".", "").replace(",", "")
    return " ".join(folded.split())


def _email_ok(value):
    return 1 if value and EMAIL_OK.match(value) else 0


def _money(cents):
    if cents is None:
        return None
    return f"{Decimal(int(cents)) / 100:.2f}"


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    # FULL OUTER JOIN needs SQLite 3.39 and group_concat(... ORDER BY ...) needs 3.44.
    # Python 3.13 on Windows, macOS and current Linux images ships a newer one.
    if sqlite3.sqlite_version_info < (3, 44):
        raise RuntimeError(f"SQLite {sqlite3.sqlite_version} is too old for the reconciliation SQL; 3.44 or newer is needed")
    conn = sqlite3.connect(str(db_path) if db_path else ":memory:")
    conn.create_function("nfold", 1, _nfold, deterministic=True)
    conn.create_function("email_ok", 1, _email_ok, deterministic=True)
    conn.create_function("money", 1, _money, deterministic=True)
    return conn


def load_csv(conn: sqlite3.Connection, table: str, path: Path) -> int:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = list(reader)
    cols = ", ".join(f'"{c}" TEXT' for c in header)
    conn.execute(f'DROP TABLE IF EXISTS "{table}"')
    conn.execute(f'CREATE TABLE "{table}" ({cols})')
    conn.executemany(f'INSERT INTO "{table}" VALUES ({", ".join("?" * len(header))})', rows)
    return len(rows)


def run_sql(conn: sqlite3.Connection, name: str) -> None:
    conn.executescript((SQL / name).read_text(encoding="utf-8"))


def query(conn: sqlite3.Connection, sql: str, params=()) -> list[dict]:
    cur = conn.execute(sql, params)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def write_csv(path: Path, rows: list[dict], columns: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = columns or (list(rows[0].keys()) if rows else [])
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def prepare_legacy(conn: sqlite3.Connection) -> dict:
    counts = {t: load_csv(conn, t, EXTRACT / f"{t}.csv") for t in LEGACY_TABLES}
    for table, file in MAP_TABLES.items():
        load_csv(conn, table, MAPS / f"{file}.csv")
    conn.execute("DROP TABLE IF EXISTS params")
    conn.execute("CREATE TABLE params (cutoff TEXT, as_of TEXT, close_month TEXT)")
    conn.execute("INSERT INTO params VALUES (?, ?, ?)",
                 (SETTINGS["history_cutoff"], SETTINGS["extract_as_of"], SETTINGS["extract_as_of"][:7]))
    run_sql(conn, "01_staging_legacy.sql")
    return counts


def _fmt(row: dict) -> dict:
    """Show cents as money in the exported detail."""
    if row.get("unit") == "cents":
        row = dict(row)
        for k in ("expected", "actual", "diff"):
            row[k] = _money(row[k])
    return row


# ------------------------------------------------------------------ profiling

def _utc_shifted(conn: sqlite3.Connection, sql: str) -> int:
    """Timestamps whose calendar date changes when New York local time is converted to UTC."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    ny, utc = ZoneInfo(SETTINGS["legacy_timezone"]), ZoneInfo("UTC")
    n = 0
    for (stamp,) in conn.execute(sql):
        local = datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S").replace(tzinfo=ny)
        n += local.astimezone(utc).date() != local.date()
    return n


def profile(out: Path) -> dict:
    conn = connect()
    counts = prepare_legacy(conn)
    run_sql(conn, "05_dq_rules.sql")
    results = query(conn, "SELECT * FROM dq_results ORDER BY rule_id")
    detail = query(conn, "SELECT * FROM dq_detail ORDER BY rule_id, source_table, record_key")
    write_csv(out / "dq_results.csv", results)
    write_csv(out / "dq_detail.csv", detail)

    facts = {
        "row_counts": counts,
        "total_rows": sum(counts.values()),
        "invoice_rows_by_type": {r["inv_type"]: r["n"] for r in query(conn, "SELECT inv_type, COUNT(*) n FROM lb_invoices GROUP BY 1")},
        "customers_by_status": {r["status"]: r["n"] for r in query(conn, "SELECT status, COUNT(*) n FROM lb_customers GROUP BY 1")},
        "customers_by_currency": {r["currency"]: r["n"] for r in query(conn, "SELECT currency, COUNT(*) n FROM lb_customers GROUP BY 1")},
        "country_spellings": {r["country"]: r["n"] for r in query(conn, "SELECT country, COUNT(*) n FROM lb_customers GROUP BY 1 ORDER BY 1")},
        "subscriptions_by_status": {r["status"]: r["n"] for r in query(conn, "SELECT status, COUNT(*) n FROM lb_subscriptions GROUP BY 1")},
        "invoices_by_status": {r["status"]: r["n"] for r in query(conn, "SELECT status, COUNT(*) n FROM lb_invoices WHERE inv_type='INV' GROUP BY 1")},
        "invoice_date_range": query(conn, "SELECT MIN(inv_date) first, MAX(inv_date) last FROM stg_invoices")[0],
        "payment_date_range": query(conn, "SELECT MIN(pay_date) first, MAX(pay_date) last FROM stg_payments")[0],
        "payments_by_method": {r["method"]: r["n"] for r in query(conn, "SELECT method, COUNT(*) n FROM lb_payments GROUP BY 1")},
        "invoices_dated_differently_in_utc": _utc_shifted(conn, "SELECT inv_ts FROM stg_invoices WHERE inv_type = 'INV'"),
        "payments_dated_differently_in_utc": _utc_shifted(conn, "SELECT pay_ts FROM stg_payments"),
        "duplicate_groups": query(conn, "SELECT COUNT(*) n FROM stg_survivors WHERE merged_count > 0")[0]["n"],
        "dq": {r["rule_id"]: r["rows_failing"] for r in results},
    }
    (out / "profile_facts.json").write_text(json.dumps(facts, indent=2) + "\n", encoding="utf-8", newline="\n")
    conn.close()
    return facts


# ------------------------------------------------------------------ reconciliation

def reconcile(run_cfg: dict, target_dir: Path, out: Path, db_path: Path | None = None) -> dict:
    if db_path and db_path.exists():
        db_path.unlink()
    conn = connect(db_path)
    prepare_legacy(conn)
    for t in TARGET_TABLES:
        load_csv(conn, f"tgt_{t}", target_dir / f"{t}.csv")
    conn.execute("CREATE TABLE checks (check_id TEXT, level TEXT, entity TEXT, title TEXT, compared INTEGER, failures INTEGER)")

    for name in ("05_dq_rules.sql", "02_expected_target.sql", "03_staging_target.sql",
                 "10_l1_completeness.sql", "20_l2_control_totals.sql", "30_l3_field_compare.sql",
                 "40_integrity.sql", "50_finance_checks.sql"):
        run_sql(conn, name)

    # Level 3: only fields inside this run's coverage count towards the result.
    coverage = run_cfg["l3_fields"]
    compared = {r["entity"]: r["rows_compared"] for r in query(conn, "SELECT * FROM l3_compared")}
    all_diffs = query(conn, "SELECT * FROM l3_diffs ORDER BY entity, legacy_key, field")
    field_summary = []
    l3_rows = []
    for check_id, entity in L3_CHECKS:
        fields = coverage[entity]
        diffs = [d for d in all_diffs if d["entity"] == entity and d["field"] in fields]
        for d in diffs:
            l3_rows.append({"check_id": check_id, **d})
        conn.execute("INSERT INTO checks VALUES (?, 'L3', ?, ?, ?, ?)",
                     (check_id, entity.replace("_", " "), f"{entity.replace('_', ' ').capitalize()}: field-level match "
                      f"({len(fields)} fields)", compared[entity] * len(fields), len(diffs)))
        for field in fields:   # fields outside this run's coverage are not reported at all
            n = sum(1 for d in diffs if d["field"] == field)
            field_summary.append({"check_id": check_id, "entity": entity, "field": field,
                                  "records_compared": compared[entity], "mismatches": n})

    # Checks added after a run are left out of that run's results (config: checks_not_in_this_run).
    skipped = set(run_cfg.get("checks_not_in_this_run", []))
    for check_id in skipped:
        conn.execute("DELETE FROM checks WHERE check_id = ?", (check_id,))
        conn.execute("DELETE FROM ri_detail WHERE check_id = ?", (check_id,))

    # A check that compared nothing has proved nothing: NO DATA, not PASS.
    checks = query(conn, "SELECT *, CASE WHEN failures > 0 THEN 'FAIL' WHEN compared = 0 THEN 'NO DATA' ELSE 'PASS' END AS result FROM checks "
                         "ORDER BY CASE level WHEN 'L1' THEN 1 WHEN 'L2' THEN 2 WHEN 'L3' THEN 3 WHEN 'RI' THEN 4 ELSE 5 END, check_id")

    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "checks.csv", checks, ["check_id", "level", "entity", "title", "compared", "failures", "result"])
    write_csv(out / "l1_bridge.csv", query(conn, "SELECT * FROM l1_bridge"))
    write_csv(out / "l1_key_differences.csv", query(conn, "SELECT * FROM l1_keys ORDER BY check_id, legacy_key"),
              ["check_id", "entity", "legacy_key", "issue"])
    write_csv(out / "l2_control_totals.csv", [_fmt(r) for r in query(conn, "SELECT * FROM l2_detail ORDER BY check_id, dimension, measure")])
    write_csv(out / "l3_field_summary.csv", field_summary)
    write_csv(out / "l3_field_differences.csv", l3_rows, ["check_id", "entity", "legacy_key", "field", "expected", "actual"])
    write_csv(out / "integrity_issues.csv", query(conn, "SELECT * FROM ri_detail ORDER BY check_id, legacy_key"),
              ["check_id", "entity", "target_key", "legacy_key", "issue"])
    write_csv(out / "l4_finance.csv", [_fmt(r) for r in query(conn, "SELECT * FROM l4_detail ORDER BY check_id, dimension")])
    exceptions = query(conn, """
        SELECT 'EX-01' AS exception_id, 'payment' AS entity, legacy_payment_id AS legacy_key,
               currency || ' ' || money(amount_c) || ', customer ' || customer AS detail
        FROM exp_payments WHERE unapplied = 'true'
        UNION ALL
        SELECT 'EX-02', 'invoice', legacy_invoice_no,
               printf('net %s + tax %s, billed %s', money(subtotal_c), money(tax_c), money(total_c))
        FROM exp_invoices WHERE total_c <> subtotal_c + tax_c
        UNION ALL
        SELECT 'EX-03', 'customer', legacy_customer_id, name FROM exp_customers WHERE email IS NULL
        UNION ALL
        SELECT 'EX-04', entity, legacy_key, reason FROM exp_rejects
        ORDER BY 1, 3""")
    write_csv(out / "accepted_exceptions.csv", exceptions, ["exception_id", "entity", "legacy_key", "detail"])

    bridge = query(conn, "SELECT * FROM l1_bridge")
    money_totals = {
        "expected_invoice_total_by_currency": {r["currency"]: _money(r["v"]) for r in query(conn, "SELECT currency, SUM(total_c) v FROM exp_invoices GROUP BY 1")},
        "actual_invoice_total_by_currency": {r["currency"]: _money(r["v"]) for r in query(conn, "SELECT currency, SUM(total_c) v FROM act_invoices GROUP BY 1")},
        "expected_payment_total_by_currency": {r["currency"]: _money(r["v"]) for r in query(conn, "SELECT currency, SUM(amount_c) v FROM exp_payments GROUP BY 1")},
        "actual_payment_total_by_currency": {r["currency"]: _money(r["v"]) for r in query(conn, "SELECT currency, SUM(amount_c) v FROM act_payments GROUP BY 1")},
        "expected_open_ar_by_currency": {r["currency"]: _money(r["v"]) for r in query(conn, "SELECT currency, SUM(balance_c) v FROM v_exp_balance GROUP BY 1")},
        "actual_open_ar_by_currency": {r["currency"]: _money(r["v"]) for r in query(conn, "SELECT currency, SUM(balance_c) v FROM v_act_balance GROUP BY 1")},
    }
    summary = {
        "run_id": run_cfg["run_id"], "label": run_cfg["label"], "run_date": run_cfg["run_date"],
        "migration_build": run_cfg["migration_build"],
        "checks_total": len(checks), "checks_passed": sum(c["result"] == "PASS" for c in checks),
        "checks_failed": [c["check_id"] for c in checks if c["result"] == "FAIL"],
        "checks_no_data": [c["check_id"] for c in checks if c["result"] == "NO DATA"],
        "by_level": {lvl: {"total": sum(c["level"] == lvl for c in checks),
                           "passed": sum(c["level"] == lvl and c["result"] == "PASS" for c in checks)}
                     for lvl in ("L1", "L2", "L3", "RI", "L4")},
        "l1_bridge": {b["entity"]: b for b in bridge},
        "l3_mismatches_by_field": {f"{r['entity']}.{r['field']}": r["mismatches"] for r in field_summary if r["mismatches"]},
        "l3_records_with_mismatch": {e: len({d["legacy_key"] for d in l3_rows if d["entity"] == e}) for _, e in L3_CHECKS},
        "money": money_totals,
        "accepted_exceptions": {ex: sum(1 for e in exceptions if e["exception_id"] == ex) for ex in ("EX-01", "EX-02", "EX-03", "EX-04")},
        "coverage_change": run_cfg.get("coverage_change", ""),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")
    conn.commit()
    conn.close()
    return summary
