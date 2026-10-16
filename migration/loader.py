"""Stand-in for the Platform team's migration loader.

In the scenario the loader belongs to the Platform team, not the data
workstream. It is reproduced here so the reconciliation has a real target to
test. Two builds are modelled:

    1.0  used in mock cutover 1 (2026-10-05), with the defects that mock found
    1.1  used in mock cutover 2 (2026-10-12), DEF-BPM-001..006 fixed

DEF-BPM-007 (payment dates converted to UTC) is in both builds. Mock 1's output
showed it but it was missed; it was raised from mock 2.

The loader reads the legacy extract and writes the platform's load files:
customers, subscriptions, invoices, credit_notes, payments and load_rejects.

    python -m migration.loader --build 1.1 --out target/mock2
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
EXTRACT = ROOT / "data" / "legacy_extract"
MAPS = ROOT / "config" / "value_maps"
SETTINGS = json.loads((ROOT / "config" / "migration_settings.json").read_text(encoding="utf-8"))

ET = ZoneInfo(SETTINGS["legacy_timezone"])
UTC = ZoneInfo("UTC")
CUTOFF = SETTINGS["history_cutoff"]

# Defect switches per build. True means the defect is present.
BUILDS = {
    "1.0": {"DEF-BPM-001": True, "DEF-BPM-002": True, "DEF-BPM-003": True, "DEF-BPM-004": True,
            "DEF-BPM-005": True, "DEF-BPM-006": True, "DEF-BPM-007": True},
    "1.1": {"DEF-BPM-001": False, "DEF-BPM-002": False, "DEF-BPM-003": False, "DEF-BPM-004": False,
            "DEF-BPM-005": False, "DEF-BPM-006": False, "DEF-BPM-007": True},
}

EMAIL_OK = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")


def _read(name: str) -> pd.DataFrame:
    return pd.read_csv(EXTRACT / f"{name}.csv", dtype=str, keep_default_na=False, encoding="utf-8")


def _map(name: str) -> pd.DataFrame:
    return pd.read_csv(MAPS / f"{name}.csv", dtype=str, keep_default_na=False, encoding="utf-8")


def _cents(series: pd.Series) -> pd.Series:
    return series.str.replace(",", "", regex=False).map(lambda v: int((Decimal(v) * 100).to_integral_value()))


def _money(cents: int) -> str:
    return f"{Decimal(cents) / 100:.2f}"


def _local_date(stamp: str) -> str:
    return stamp[:10]


def _utc_date(stamp: str) -> str:
    local = datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S").replace(tzinfo=ET)
    return local.astimezone(UTC).date().isoformat()


def _parse_created(value: str) -> str:
    if re.fullmatch(r"\d{2}/\d{2}/\d{4}", value):
        return datetime.strptime(value, "%m/%d/%Y").date().isoformat()
    return value


def _norm_name(value: str) -> str:
    return " ".join(value.casefold().replace(".", "").replace(",", "").split())


def run(build: str, out: Path) -> dict:
    bugs = BUILDS[build]
    out.mkdir(parents=True, exist_ok=True)

    cust = _read("lb_customers")
    subs = _read("lb_subscriptions")
    inv = _read("lb_invoices")
    pay = _read("lb_payments")

    country = dict(_map("country_map")[["legacy_value", "iso2"]].values)
    cust_status = _map("customer_status_map").set_index("legacy_status")
    sub_status = _map("subscription_status_map").set_index("legacy_status")
    inv_status = dict(_map("invoice_status_map")[["legacy_status", "target_status"]].values)
    plan = dict(_map("plan_map")[["legacy_plan_code", "target_plan_id"]].values)
    method = dict(_map("payment_method_map")[["legacy_method", "target_method"]].values)
    tax_rate = {r: float(v) for r, v in _map("tax_rates")[["tax_region", "rate"]].values}

    # ---- clean ----------------------------------------------------------------
    for df in (cust, subs, inv, pay):
        df["cust_id"] = df["cust_id"].str.strip()
    cust["created"] = cust["created_on"].map(_parse_created)
    cust["email_clean"] = cust["contact_email"].str.strip()
    cust["email_ok"] = cust["email_clean"].map(lambda e: bool(EMAIL_OK.match(e)))

    # ---- duplicate customers: survivorship ---------------------------------------
    cust["dup_key"] = [f"{_norm_name(n)}|{e.lower()}" if ok else f"__{cid}"
                       for n, e, ok, cid in zip(cust["company_name"], cust["email_clean"], cust["email_ok"], cust["cust_id"])]
    cust = cust.sort_values(["dup_key", "created", "cust_id"])
    cust["survivor"] = cust.groupby("dup_key")["cust_id"].transform("first")
    survivor_of = dict(zip(cust["cust_id"], cust["survivor"]))
    merged_ids = (cust[cust["cust_id"] != cust["survivor"]].groupby("survivor")["cust_id"]
                  .apply(lambda s: ";".join(sorted(s))).to_dict())
    rank = {"H": 0, "A": 1, "I": 2}
    group_status = cust.groupby("survivor")["status"].agg(lambda s: min(s, key=rank.get)).to_dict()

    for df in (subs, inv, pay):
        df["owner"] = df["cust_id"].map(survivor_of)

    # ---- normalise invoices and payments -----------------------------------------
    inv["sub_id"] = inv["sub_id"].where(inv["sub_id"] != "", None)
    inv["inv_date"] = inv["inv_ts"].map(_local_date)
    for col in ("net_amount", "tax_amount", "gross_amount"):
        inv[col + "_c"] = _cents(inv[col])
    pay["pay_date"] = pay["pay_ts"].map(_local_date)
    pay["amount_c"] = _cents(pay["amount"])
    pay["inv_no"] = pay["inv_no"].where(pay["inv_no"] != "", None)

    # ---- scope -----------------------------------------------------------------
    is_inv = inv["inv_type"] == "INV"
    inv_in = is_inv & ((inv["inv_date"] >= CUTOFF) | inv["status"].isin(["OPEN", "PART"]))
    owners_with_activity = set(inv.loc[inv_in, "owner"])
    survivors = cust[cust["cust_id"] == cust["survivor"]].copy()
    survivors["group_status"] = survivors["cust_id"].map(group_status)
    survivors = survivors[survivors["group_status"].isin(["A", "H"]) | survivors["cust_id"].isin(owners_with_activity)]
    in_scope_customers = set(survivors["cust_id"])

    inv_in &= inv["owner"].isin(in_scope_customers)
    in_scope_inv_nos = set(inv.loc[inv_in, "inv_no"])
    crn_in = (inv["inv_type"] == "CRN") & inv["orig_inv_no"].isin(in_scope_inv_nos)

    referenced_subs = set(inv.loc[inv_in, "sub_id"].dropna())
    subs_in = (subs["owner"].isin(in_scope_customers) & (subs["status"] != "PEND")
               & (subs["status"].isin(["ACT", "TRL", "SUSP", "PAUS"]) | (subs["end_date"] >= CUTOFF)
                  | subs["sub_id"].isin(referenced_subs)))
    if bugs["DEF-BPM-004"]:
        # Merge step re-pointed invoices and payments but dropped the merged-away customer's subscriptions.
        subs_in &= subs["cust_id"] == subs["owner"]

    all_legacy_numbers = set(inv["inv_no"])
    orphan = pay["inv_no"].isna() | ~pay["inv_no"].isin(all_legacy_numbers)
    pay_in = (pay["inv_no"].isin(in_scope_inv_nos)
              | (orphan & (pay["pay_date"] >= CUTOFF) & pay["owner"].isin(in_scope_customers)))

    # ---- customers ----------------------------------------------------------------
    survivors = survivors.sort_values("cust_id").reset_index(drop=True)
    survivors["customer_id"] = [f"cus_{i:06d}" for i in range(1, len(survivors) + 1)]
    cus_id = dict(zip(survivors["cust_id"], survivors["customer_id"]))
    t_cust = pd.DataFrame({
        "customer_id": survivors["customer_id"],
        "legacy_customer_id": survivors["cust_id"],
        "merged_legacy_ids": survivors["cust_id"].map(merged_ids).fillna(""),
        "name": survivors["company_name"],
        "email": [e if ok else "" for e, ok in zip(survivors["email_clean"], survivors["email_ok"])],
        "country": survivors["country"].map(country),
        "currency": survivors["currency"],
        "created_date": survivors["created"],
        "status": survivors["group_status"].map(cust_status["target_status"]),
        "invoice_hold": survivors["group_status"].map(cust_status["invoice_hold"]),
    })

    # ---- subscriptions ------------------------------------------------------------
    s = subs[subs_in].sort_values("sub_id").copy()
    status_map = sub_status["target_status"].to_dict()
    if bugs["DEF-BPM-002"]:
        status_map = {k: v for k, v in status_map.items() if k not in ("SUSP", "PAUS")}
    s["target_status"] = s["status"].map(status_map).fillna("active")   # platform default when blank
    s["cancel_reason"] = s["status"].map(sub_status["cancel_reason"]).fillna("")
    rejected_subs = s[s["seats"].astype(int) < 1]
    s = s[s["seats"].astype(int) >= 1].reset_index(drop=True)
    s["subscription_id"] = [f"sub_{i:06d}" for i in range(1, len(s) + 1)]
    sub_tid = dict(zip(s["sub_id"], s["subscription_id"]))
    t_subs = pd.DataFrame({
        "subscription_id": s["subscription_id"], "legacy_subscription_id": s["sub_id"],
        "customer_id": s["owner"].map(cus_id), "plan_id": s["plan_code"].map(plan),
        "quantity": s["seats"].astype(int), "start_date": s["start_date"], "end_date": s["end_date"],
        "status": s["target_status"], "cancel_reason": s["cancel_reason"],
    })

    # ---- payments applied per invoice (needed for amount_paid) ---------------------
    p = pay[pay_in].copy()
    p["orphan"] = orphan[pay_in]
    paid_c = p[~p["orphan"]].groupby("inv_no")["amount_c"].sum().to_dict()

    # ---- invoices and credit notes ------------------------------------------------------
    i = inv[inv_in].sort_values("inv_no").copy()
    c = inv[crn_in].sort_values("inv_no").copy()
    if bugs["DEF-BPM-006"]:
        # Credit notes went through the invoice mapping as negative invoices.
        c["status"] = "ISSUED"
        i = pd.concat([i, c]).sort_values("inv_no")
        c = c.iloc[0:0]
    i = i.reset_index(drop=True)
    i["invoice_id"] = [f"in_{k:07d}" for k in range(1, len(i) + 1)]
    inv_tid = dict(zip(i["inv_no"], i["invoice_id"]))

    date_fn = _utc_date if bugs["DEF-BPM-001"] else _local_date
    i["invoice_date"] = i["inv_ts"].map(date_fn)
    if bugs["DEF-BPM-005"]:
        # Platform recalculated tax from the region rate instead of importing legacy tax.
        rate = i["owner"].map(dict(zip(cust["cust_id"], cust["tax_region"]))).map(tax_rate)
        i["tax_c"] = [int(round(round(n / 100 * r, 2) * 100)) for n, r in zip(i["net_amount_c"], rate)]
        i["total_c"] = i["net_amount_c"] + i["tax_c"]
    else:
        i["tax_c"] = i["tax_amount_c"]
        i["total_c"] = i["gross_amount_c"]
    i["paid_c"] = i["inv_no"].map(paid_c).fillna(0).astype(int)
    i["target_status"] = i["status"].map(inv_status).fillna("open")
    i["due_c"] = [t - pd_ if st in ("open", "uncollectible") else 0
                  for t, pd_, st in zip(i["total_c"], i["paid_c"], i["target_status"])]
    t_inv = pd.DataFrame({
        "invoice_id": i["invoice_id"], "legacy_invoice_no": i["inv_no"], "customer_id": i["owner"].map(cus_id),
        "subscription_id": i["sub_id"].map(sub_tid).fillna(""), "invoice_date": i["invoice_date"],
        "due_date": i["due_date"], "currency": i["currency"],
        "subtotal": i["net_amount_c"].map(_money), "tax": i["tax_c"].map(_money), "total": i["total_c"].map(_money),
        "amount_paid": i["paid_c"].map(_money), "amount_due": i["due_c"].map(_money), "status": i["target_status"],
    })

    c = c.reset_index(drop=True)
    t_crn = pd.DataFrame({
        "credit_note_id": [f"cn_{k:06d}" for k in range(1, len(c) + 1)],
        "legacy_credit_note_no": c["inv_no"], "invoice_id": c["orig_inv_no"].map(inv_tid),
        "customer_id": c["owner"].map(cus_id), "credit_date": c["inv_ts"].map(_local_date),
        "currency": c["currency"], "subtotal": (-c["net_amount_c"]).map(_money),
        "tax": (-c["tax_amount_c"]).map(_money), "total": (-c["gross_amount_c"]).map(_money),
    })

    # ---- payments -------------------------------------------------------------------
    p = p.sort_values("pay_id").reset_index(drop=True)
    p_orphan = p["orphan"]
    t_pay = pd.DataFrame({
        "payment_id": [f"py_{k:07d}" for k in range(1, len(p) + 1)],
        "legacy_payment_id": p["pay_id"], "customer_id": p["owner"].map(cus_id),
        "invoice_id": [("" if o else inv_tid.get(n, "")) for n, o in zip(p["inv_no"], p_orphan)],
        "paid_date": p["pay_ts"].map(_utc_date if bugs["DEF-BPM-007"] else _local_date),
        "currency": "USD" if bugs["DEF-BPM-003"] else p["currency"],
        "amount": p["amount_c"].map(_money), "method": p["method"].map(method),
        "unapplied": p_orphan.map({True: "true", False: "false"}),
    })

    rejects = pd.DataFrame({
        "entity": "subscription", "legacy_key": rejected_subs["sub_id"],
        "reason": "quantity must be at least 1",
    })

    files = {"customers": t_cust, "subscriptions": t_subs, "invoices": t_inv, "credit_notes": t_crn,
             "payments": t_pay, "load_rejects": rejects}
    for name, df in files.items():
        df.to_csv(out / f"{name}.csv", index=False, encoding="utf-8")
    counts = {name: len(df) for name, df in files.items()}
    (out / "load_report.json").write_text(json.dumps({"build": build, "counts": counts}, indent=2) + "\n",
                                         encoding="utf-8", newline="\n")
    return counts


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--build", choices=sorted(BUILDS), required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    print(json.dumps(run(args.build, args.out), indent=2))


if __name__ == "__main__":
    main()
