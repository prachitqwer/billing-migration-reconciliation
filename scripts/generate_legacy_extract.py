"""Generate the legacy billing extract used by both mock cutovers.

Builds the fictional Northstar legacy extract: five tables with the kinds of
problems a home-grown billing system collects over the years (padded ids,
free-text countries, duplicate customers, credit notes stored as negative
invoices, and the rest of docs/02_data_profiling_report.md).

Everything is driven by one seed, so the files are identical on every run.

    python scripts/generate_legacy_extract.py            # writes data/legacy_extract/*.csv
"""

from __future__ import annotations

import csv
import random
import sys
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "legacy_extract"

SEED = 20260930
AS_OF = date(2026, 9, 30)            # extract taken after the September close
HISTORY_START = date(2023, 10, 1)    # legacy keeps 36 months online
N_CUSTOMERS = 1200
N_DUPLICATES = 27
N_ORPHAN_PAYMENTS = 23
N_ZERO_SEAT_SUBS = 6

CENT = Decimal("0.01")

# ---------------------------------------------------------------- reference data

CURRENCY_MIX = [("USD", 70), ("CAD", 12), ("GBP", 10), ("EUR", 8)]
FX_LIST_PRICE = {"USD": Decimal("1"), "CAD": Decimal("1.35"), "GBP": Decimal("0.80"), "EUR": Decimal("0.92")}

COUNTRY_BY_CCY = {"USD": ["US"], "CAD": ["CA"], "GBP": ["GB"], "EUR": ["DE", "FR", "NL", "IE"]}
COUNTRY_SPELLINGS = {
    "US": [("US", 55), ("USA", 25), ("United States", 15), ("U.S.", 5)],
    "CA": [("CA", 70), ("Canada", 30)],
    "GB": [("GB", 40), ("UK", 45), ("United Kingdom", 15)],
    "DE": [("DE", 60), ("Germany", 40)],
    "FR": [("FR", 60), ("France", 40)],
    "NL": [("NL", 70), ("Netherlands", 30)],
    "IE": [("IE", 70), ("Ireland", 30)],
}
TLD = {"US": "com", "CA": "ca", "GB": "co.uk", "DE": "de", "FR": "fr", "NL": "nl", "IE": "ie"}

# tax region -> rate. EU B2B customers are mostly reverse charge (0 %).
TAX_REGIONS = {
    "US": [("US-NY", "0.08875", 14), ("US-CA", "0.0725", 0), ("US-TX", "0.0625", 16), ("US-WA", "0.065", 12),
           ("US-MA", "0.0625", 9), ("US-NC", "0.0475", 8), ("US-FL", "0.06", 7), ("US-IL", "0.0625", 6),
           ("US-EX", "0", 28)],
    "CA": [("CA-ON", "0.13", 55), ("CA-BC", "0.12", 25), ("CA-QC", "0.14975", 20)],
    "GB": [("GB-STD", "0.20", 100)],
    "DE": [("EU-RC", "0", 70), ("DE-STD", "0.19", 30)],
    "FR": [("EU-RC", "0", 70), ("FR-STD", "0.20", 30)],
    "NL": [("EU-RC", "0", 70), ("NL-STD", "0.21", 30)],
    "IE": [("EU-RC", "0", 70), ("IE-STD", "0.23", 30)],
}

# plan code, name, period, USD price per seat per month
PLANS = [
    ("STR-M", "Starter", "M", "15"),
    ("STR-A", "Starter (annual)", "A", "15"),
    ("PRO-M", "Professional", "M", "35"),
    ("PRO-A", "Professional (annual)", "A", "35"),
    ("BUS-M", "Business", "M", "60"),
    ("BUS-A", "Business (annual)", "A", "60"),
    ("ENT-A", "Enterprise (annual)", "A", "95"),
    ("ADD-SSO-M", "Add-on: SSO", "M", "4"),
    ("ADD-API-M", "Add-on: API access", "M", "6"),
    ("ADD-STO-M", "Add-on: extra storage", "M", "3"),
]
# Retired plans: deleted from the plan table years ago, still referenced by old subscriptions.
RETIRED_PLANS = [("LEG-PRO-2019", "M", "29"), ("LEG-TEAM-2020", "M", "49")]
ANNUAL_DISCOUNT = Decimal("0.85")

NAME_A = ["Blue", "North", "Silver", "Cedar", "Harbor", "Summit", "Granite", "Maple", "Iron", "Copper", "Pine",
          "River", "Falcon", "Atlas", "Beacon", "Clear", "Crest", "Delta", "Echo", "Ember", "Fox", "Frontier",
          "Golden", "Hollow", "Juniper", "Keystone", "Lake", "Lantern", "Meridian", "Mosaic", "Oak", "Orbit",
          "Pioneer", "Prairie", "Quarry", "Redwood", "Ridge", "Sage", "Shore", "Signal", "Stone", "Tidal",
          "Union", "Vantage", "Willow", "Zenith", "Anchor", "Bright", "Canyon", "Driftwood", "Alder", "Basin",
          "Birch", "Bluff", "Brook", "Cobalt", "Coral", "Cypress", "Dune", "Elm", "Fjord", "Glacier", "Hawk",
          "Heron", "Indigo", "Ivory", "Kestrel", "Laurel", "Linden", "Marble", "Mesa", "Northwind", "Osprey",
          "Pebble", "Raven", "Saddle", "Spruce", "Sterling", "Thistle", "Timber", "Vista", "Wren"]
NAME_B = ["Analytics", "Logistics", "Health", "Dental", "Legal", "Labs", "Freight", "Media", "Foods", "Robotics",
          "Insurance", "Realty", "Pharma", "Energy", "Software", "Consulting", "Design", "Retail", "Outfitters",
          "Capital", "Clinics", "Engineering", "Builders", "Partners", "Systems", "Studios", "Marine",
          "Telecom", "Learning", "Supply", "Brewing", "Veterinary", "Staffing", "Printing", "Hospitality",
          "Aviation", "Solar", "Fitness", "Accounting", "Architects"]
SUFFIX = {"US": ["Inc", "LLC", "Corp", "Co", "Group"], "CA": ["Inc", "Ltd", "Corp"], "GB": ["Ltd", "PLC", "LLP"],
          "IE": ["Ltd", "DAC"], "DE": ["GmbH", "AG"], "FR": ["SARL", "SAS"], "NL": ["BV", "NV"]}
DE_WORDS = ["Müller", "Schröder", "Bäcker", "Weiß", "Groß", "Köhler", "Sommer", "Fischer", "Krämer", "Böhm",
            "Hoffmann", "Jäger", "Vogel", "Schäfer", "Lehmann", "Brückner"]
FR_WORDS = ["Lumière", "Côté", "Élan", "Château", "Forêt", "Rivière", "Étoile", "Garçon", "Mercier", "Fénelon",
            "Lefèvre", "Aubert", "Bérard", "Dupré", "Rémy", "Granger"]
DE_TRADES = ["Logistik", "Technik", "Bau", "Software", "Medien", "Handel", "Maschinen", "Verlag", "Elektro", "Pflege"]
FR_TRADES = ["Conseil", "Logistique", "Santé", "Médias", "Bâtiment", "Informatique", "Transports", "Énergie",
             "Imprimerie", "Ingénierie"]
EMAIL_BOXES = ["billing", "ap", "accounts.payable", "finance", "invoices"]


def pick(rng: random.Random, weighted):
    items, weights = zip(*[(w[:-1] if len(w) > 2 else w[0], w[-1]) for w in weighted])
    return rng.choices(items, weights=weights, k=1)[0]


def money(x) -> Decimal:
    return Decimal(x).quantize(CENT, rounding=ROUND_HALF_UP)


def fmt_amount(rng: random.Random, value: Decimal) -> str:
    """Legacy export writes ~7 % of amounts with a thousands separator."""
    if abs(value) >= 1000 and rng.random() < 0.07:
        return f"{value:,.2f}"
    return f"{value:.2f}"


def month_add(d: date, months: int) -> date:
    y, m = divmod(d.month - 1 + months, 12)
    return date(d.year + y, m + 1, min(d.day, 28))


def last_day_of_month(d: date) -> date:
    nxt = date(d.year + (d.month // 12), d.month % 12 + 1, 1)
    return nxt - timedelta(days=1)


def ts(d: date, rng: random.Random, kind: str) -> str:
    """Local (America/New_York) timestamp the way the legacy system stores it."""
    if kind == "batch":                       # nightly billing run
        h, m = 2, rng.randint(0, 89)
        h, m = h + m // 60, m % 60
    elif kind == "evening":                   # month-end true-ups raised late
        h, m = rng.randint(16, 23), rng.randint(0, 59)
    else:                                     # people working during the day, some late
        h = rng.choices(range(7, 24), weights=[2, 6, 9, 9, 9, 8, 8, 9, 9, 8, 6, 4, 3, 3, 3, 2, 2])[0]
        m = rng.randint(0, 59)
    return datetime(d.year, d.month, d.day, h, m, rng.randint(0, 59)).strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------- generation

def build():
    rng = random.Random(SEED)

    # ---- customers -------------------------------------------------------
    customers = []
    used_names, used_domains = set(), set()
    cust_no = 100000
    for _ in range(N_CUSTOMERS):
        cust_no += rng.randint(1, 4)
        ccy = pick(rng, CURRENCY_MIX)
        iso = rng.choice(COUNTRY_BY_CCY[ccy])
        for attempt in range(500):
            if iso == "DE":
                name = f"{rng.choice(DE_WORDS)} {rng.choice(DE_TRADES)} {rng.choice(SUFFIX[iso])}"
            elif iso == "FR":
                name = f"{rng.choice(FR_WORDS)} {rng.choice(FR_TRADES)} {rng.choice(SUFFIX[iso])}"
            else:
                name = f"{rng.choice(NAME_A)} {rng.choice(NAME_B)} {rng.choice(SUFFIX[iso])}"
            core = name.rsplit(" ", 1)[0]
            slug = "".join(ch for ch in core.lower().replace(" ", "")
                           .translate(str.maketrans("äöüßéèêôçâ", "aousseeoca")) if ch.isalnum())
            domain = f"{slug}.{TLD[iso]}"
            if name.lower() not in used_names and domain not in used_domains:
                used_names.add(name.lower())
                used_domains.add(domain)
                break
        else:
            raise RuntimeError(f"ran out of unique company names for {iso}")
        created = date(2016, 1, 4) + timedelta(days=int((rng.random() ** 0.55) * (date(2026, 8, 31) - date(2016, 1, 4)).days))
        r = rng.random()
        if r < 0.025:
            email = rng.choice(["", "n/a", f"{rng.choice(EMAIL_BOXES)}@", f"{rng.choice(EMAIL_BOXES)}@{slug}"])
        else:
            email = f"{rng.choice(EMAIL_BOXES)}@{domain}"
        customers.append({
            "cust_id": f"C{cust_no:06d}", "company_name": name, "contact_email": email,
            "country": pick(rng, COUNTRY_SPELLINGS[iso]), "iso": iso, "currency": ccy,
            "tax_region": pick(rng, [(c, w) for c, _, w in TAX_REGIONS[iso]]),
            "created": created, "status": None,
        })
    tax_rate = {c: Decimal(r) for regions in TAX_REGIONS.values() for c, r, _ in regions}

    # duplicates: same company and email entered twice by Sales, later customer id
    dup_sources = rng.sample([c for c in customers if "@" in c["contact_email"] and "." in c["contact_email"].split("@")[1]
                              and c["created"] < date(2025, 6, 1)], N_DUPLICATES)
    dup_pairs = []
    for src in dup_sources:
        cust_no += rng.randint(1, 4)
        variant = rng.choice([src["company_name"].upper(), src["company_name"] + ".", src["company_name"].replace(" ", "  ", 1),
                              src["company_name"].lower().title()])
        email = src["contact_email"].upper() if rng.random() < 0.5 else src["contact_email"].capitalize()
        dup = dict(src, cust_id=f"C{cust_no:06d}", company_name=variant, contact_email=email,
                   country=pick(rng, COUNTRY_SPELLINGS[src["iso"]]),
                   created=src["created"] + timedelta(days=rng.randint(20, 400)))
        if dup["created"] > date(2026, 8, 31):
            dup["created"] = date(2026, 8, 31) - timedelta(days=rng.randint(0, 60))
        customers.append(dup)
        dup_pairs.append((src, dup))

    # ---- subscriptions -----------------------------------------------------
    subs = []
    sub_no = 500000
    dup_ids = {d["cust_id"] for _, d in dup_pairs}
    for c in customers:
        n = 1 if c["cust_id"] in dup_ids else rng.choices([1, 2, 3], weights=[60, 30, 10])[0]
        for k in range(n):
            sub_no += 1
            if k == 0:
                if c["created"] < date(2021, 1, 1) and rng.random() < 0.18:
                    code, period, price = rng.choice(RETIRED_PLANS)
                else:
                    code, _, period, price = rng.choices(PLANS[:7], weights=[18, 6, 26, 9, 16, 8, 6])[0]
            else:
                code, _, period, price = rng.choice(PLANS[7:])
            start = c["created"] + timedelta(days=rng.randint(0, 120) if k == 0 else rng.randint(30, 900))
            if start > AS_OF:
                start = AS_OF - timedelta(days=rng.randint(40, 200))
            if start < c["created"]:
                start = c["created"]
            seats = max(1, int(rng.lognormvariate(2.3, 1.0))) if not code.startswith("ADD") else rng.randint(1, 40)
            seats = min(seats, 400)
            r = rng.random()
            if r < 0.20:
                status = "CANC"
            elif r < 0.27:
                status = "EXP"
            elif r < 0.31:
                status = "SUSP"
            elif r < 0.33:
                status = "PAUS"
            else:
                status = "ACT"
            end = None
            if status in ("CANC", "EXP"):
                span = (AS_OF - start).days
                end = start + timedelta(days=max(31, int(span * rng.uniform(0.15, 0.98))))
                if end > AS_OF:
                    end = AS_OF - timedelta(days=rng.randint(1, 20))
                if end <= start:
                    end = start + timedelta(days=31)
            subs.append({"sub_id": f"S{sub_no}", "cust_id": c["cust_id"], "plan_code": code, "period": period,
                         "price": Decimal(price), "seats": seats, "start": start, "end": end, "status": status})
    # trials and pending activations (not billed yet)
    for c in rng.sample(customers[:N_CUSTOMERS], 35):
        sub_no += 1
        code, _, period, price = rng.choice(PLANS[:6])
        start = AS_OF - timedelta(days=rng.randint(1, 25))
        subs.append({"sub_id": f"S{sub_no}", "cust_id": c["cust_id"], "plan_code": code, "period": period,
                     "price": Decimal(price), "seats": rng.randint(2, 30), "start": start, "end": None, "status": "TRL"})
    for c in rng.sample(customers[:N_CUSTOMERS], 24):
        sub_no += 1
        code, _, period, price = rng.choice(PLANS[:6])
        start = AS_OF + timedelta(days=rng.randint(3, 40))
        subs.append({"sub_id": f"S{sub_no}", "cust_id": c["cust_id"], "plan_code": code, "period": period,
                     "price": Decimal(price), "seats": rng.randint(2, 50), "start": start, "end": None, "status": "PEND"})
    # zero-seat cancelled subscriptions keyed in error and never billed
    for c in rng.sample(customers[:N_CUSTOMERS], N_ZERO_SEAT_SUBS):
        sub_no += 1
        start = date(2024, rng.randint(9, 12), rng.randint(1, 28))
        subs.append({"sub_id": f"S{sub_no}", "cust_id": c["cust_id"], "plan_code": "PRO-M", "period": "M",
                     "price": Decimal("35"), "seats": 0, "start": start,
                     "end": start + timedelta(days=rng.randint(35, 90)), "status": "CANC", "never_billed": True})

    cust_by_id = {c["cust_id"]: c for c in customers}

    # ---- invoices ----------------------------------------------------------
    invoices = []
    inv_no = 7000000
    recent = AS_OF - timedelta(days=60)

    def add_invoice(c, sub, d, net, kind):
        nonlocal inv_no
        inv_no += 1
        rate = tax_rate[c["tax_region"]]
        tax = money(net * rate)
        gross = net + tax
        if rng.random() < 0.004:                          # legacy one-cent rounding bug
            gross += rng.choice([CENT, -CENT])
        rec = {"inv_no": f"INV{inv_no}", "cust_id": c["cust_id"], "sub_id": sub["sub_id"] if sub else "",
               "inv_ts": ts(d, rng, kind), "inv_date": d, "terms": 30 if c["iso"] in ("US", "CA") else 14,
               "currency": c["currency"], "net": net, "tax": tax, "gross": gross, "type": "INV",
               "orig_inv_no": "", "status": None, "sub_status": sub["status"] if sub else ""}
        invoices.append(rec)
        return rec

    for s in subs:
        if s["status"] in ("TRL", "PEND") or s.get("never_billed"):
            continue
        c = cust_by_id[s["cust_id"]]
        fx = FX_LIST_PRICE[c["currency"]]
        seat_price = money(s["price"] * fx)
        step = 1 if s["period"] == "M" else 12
        d = s["start"].replace(day=min(s["start"].day, 28))
        stop = s["end"] or AS_OF
        if s["status"] == "PAUS":
            stop = min(stop, AS_OF - timedelta(days=rng.randint(30, 150)))
        while d <= stop and d <= AS_OF:
            if d >= HISTORY_START:
                net = seat_price * s["seats"] * (12 * ANNUAL_DISCOUNT if step == 12 else 1)
                add_invoice(c, s, d, money(net), "batch")
            d = month_add(d, step)

    # one-off invoices (overage, services, true-ups). A third land on the last day of a month, late.
    billed_customers = sorted({i["cust_id"] for i in invoices})
    n_oneoff = int(len(invoices) * 0.045)
    for _ in range(n_oneoff):
        c = cust_by_id[rng.choice(billed_customers)]
        m = month_add(HISTORY_START, rng.randint(0, 35))
        if rng.random() < 0.33:
            d, kind = last_day_of_month(m), "evening"
        else:
            d, kind = m.replace(day=rng.randint(1, 28)), "manual"
        if d > AS_OF or d < c["created"]:
            continue
        net = money(Decimal(rng.randint(150_00, 2_500_000)) / 100 * FX_LIST_PRICE[c["currency"]])
        add_invoice(c, None, d, net, kind)

    invoices.sort(key=lambda r: (r["inv_ts"], r["cust_id"]))
    for i, r in enumerate(invoices, start=7000001):  # number in issue order, the way legacy does
        r["inv_no"] = f"INV{i}"

    # statuses
    open_by_sub = {}
    for r in sorted(invoices, key=lambda r: r["inv_date"], reverse=True):
        if r["sub_status"] == "SUSP":
            k = open_by_sub.get(r["sub_id"], 0)
            if k < 3:
                r["status"] = "OPEN"
                open_by_sub[r["sub_id"]] = k + 1
                continue
        if r["inv_date"] >= recent:
            r["status"] = pick(rng, [("PAID", 80), ("OPEN", 15), ("PART", 3), ("VOID", 2)])
        else:
            r["status"] = pick(rng, [("PAID", 97.0), ("WO", 1.0), ("VOID", 1.5), ("OPEN", 0.5)])

    # credit notes: stored in the invoice table as negative invoices
    crns = []
    for r in invoices:
        if r["status"] == "PAID" and rng.random() < 0.02:
            share = Decimal(rng.choice([10, 25, 50, 100])) / 100
            d = r["inv_date"] + timedelta(days=rng.randint(5, 40))
            if d > AS_OF:
                continue
            net = -money(r["net"] * share)
            tax = -money(r["tax"] * share)
            crns.append({"inv_no": None, "cust_id": r["cust_id"], "sub_id": r["sub_id"], "inv_ts": ts(d, rng, "manual"),
                         "inv_date": d, "terms": 0, "currency": r["currency"], "net": net, "tax": tax, "gross": net + tax,
                         "type": "CRN", "orig_inv_no": r["inv_no"], "status": "ISSUED", "sub_status": ""})
    crn_no = 8000000
    for r in sorted(crns, key=lambda r: r["inv_ts"]):
        crn_no += 1
        r["inv_no"] = f"CRN{crn_no}"
    invoices.extend(crns)

    # ---- payments ----------------------------------------------------------
    payments = []
    methods = {"USD": [("CARD", 55), ("ACH", 35), ("WIRE", 6), ("CHK", 4)], "CAD": [("CARD", 60), ("EFT", 30), ("WIRE", 10)],
               "GBP": [("CARD", 50), ("BACS", 40), ("WIRE", 10)], "EUR": [("CARD", 45), ("SEPA", 45), ("WIRE", 10)]}

    def pay(r, amount, d, method):
        if method == "CARD" and d == r["inv_date"]:
            t = (datetime.strptime(r["inv_ts"], "%Y-%m-%d %H:%M:%S") + timedelta(minutes=rng.randint(1, 50)))
            stamp = t.strftime("%Y-%m-%d %H:%M:%S")
        else:
            stamp = ts(d, rng, "manual")
        payments.append({"cust_id": r["cust_id"], "inv_no": r["inv_no"], "pay_ts": stamp, "amount": amount,
                         "currency": r["currency"], "method": method})

    for r in invoices:
        if r["type"] != "INV" or r["status"] in ("OPEN", "VOID"):
            continue
        method = pick(rng, methods[r["currency"]])
        lag = 0 if method == "CARD" and rng.random() < 0.85 else rng.randint(1, 45)
        d = r["inv_date"] + timedelta(days=lag)
        if d > AS_OF:
            d = AS_OF
        if r["status"] == "PAID":
            if rng.random() < 0.05 and r["gross"] > 100:
                first = money(r["gross"] * Decimal(rng.uniform(0.3, 0.7)))
                pay(r, first, d, method)
                d2 = min(AS_OF, d + timedelta(days=rng.randint(5, 30)))
                pay(r, r["gross"] - first, d2, method)
            else:
                pay(r, r["gross"], d, method)
        elif r["status"] == "PART":
            pay(r, money(r["gross"] * Decimal(rng.uniform(0.2, 0.8))), d, method)
        elif r["status"] == "WO" and rng.random() < 0.3:
            pay(r, money(r["gross"] * Decimal(rng.uniform(0.1, 0.5))), d, method)

    # orphan payments: invoice number keyed wrong, or left blank
    real_numbers = {r["inv_no"] for r in invoices}
    for _ in range(N_ORPHAN_PAYMENTS):
        c = cust_by_id[rng.choice(billed_customers)]
        d = AS_OF - timedelta(days=rng.randint(3, 330))
        bad = "" if rng.random() < 0.4 else f"INV{rng.randint(7000001, 7099999)}"
        while bad in real_numbers:
            bad = f"INV{rng.randint(7100000, 7199999)}"
        payments.append({"cust_id": c["cust_id"], "inv_no": bad, "pay_ts": ts(d, rng, "manual"),
                         "amount": money(Decimal(rng.randint(5_000, 900_000)) / 100), "currency": c["currency"],
                         "method": pick(rng, methods[c["currency"]])})

    payments.sort(key=lambda p: (p["pay_ts"], p["cust_id"]))
    for i, p in enumerate(payments, start=3000001):
        p["pay_id"] = f"P{i}"

    # ---- customer status -----------------------------------------------------
    live = {s["cust_id"] for s in subs if s["status"] in ("ACT", "SUSP", "PAUS", "TRL")}
    for c in customers:
        if c["cust_id"] in live:
            c["status"] = "H" if rng.random() < 0.02 else "A"
        else:
            c["status"] = "I"

    return customers, subs, invoices, payments, dup_pairs


def write(customers, subs, invoices, payments, out: Path = OUT):
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED + 1)  # separate stream for cosmetic export noise

    with open(out / "lb_customers.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["cust_id", "company_name", "contact_email", "country", "currency", "tax_region", "created_on", "status"])
        for c in sorted(customers, key=lambda c: c["cust_id"]):
            created = c["created"].strftime("%m/%d/%Y") if rng.random() < 0.18 else c["created"].isoformat()
            w.writerow([c["cust_id"], c["company_name"], c["contact_email"], c["country"], c["currency"],
                        c["tax_region"], created, c["status"]])

    with open(out / "lb_plans.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["plan_code", "plan_name", "billing_period", "price_usd_per_seat_month"])
        for code, name, period, price in PLANS:
            w.writerow([code, name, period, price])

    with open(out / "lb_subscriptions.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sub_id", "cust_id", "plan_code", "seats", "start_date", "end_date", "status"])
        for s in sorted(subs, key=lambda s: s["sub_id"]):
            w.writerow([s["sub_id"], s["cust_id"], s["plan_code"], s["seats"], s["start"].isoformat(),
                        s["end"].isoformat() if s["end"] else "", s["status"]])

    with open(out / "lb_invoices.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["inv_no", "inv_type", "orig_inv_no", "cust_id", "sub_id", "inv_ts", "due_date", "currency",
                    "net_amount", "tax_amount", "gross_amount", "status"])
        for r in sorted(invoices, key=lambda r: r["inv_no"]):
            cust = r["cust_id"] + (" " if rng.random() < 0.01 else "")
            due = (r["inv_date"] + timedelta(days=r["terms"])).isoformat() if r["type"] == "INV" else ""
            w.writerow([r["inv_no"], r["type"], r["orig_inv_no"], cust, r["sub_id"], r["inv_ts"], due, r["currency"],
                        fmt_amount(rng, r["net"]), fmt_amount(rng, r["tax"]), fmt_amount(rng, r["gross"]), r["status"]])

    with open(out / "lb_payments.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["pay_id", "cust_id", "inv_no", "pay_ts", "amount", "currency", "method"])
        for p in payments:
            cust = p["cust_id"] + ("  " if rng.random() < 0.025 else "")
            w.writerow([p["pay_id"], cust, p["inv_no"], p["pay_ts"], fmt_amount(rng, p["amount"]), p["currency"], p["method"]])


def main(out: Path = OUT) -> int:
    customers, subs, invoices, payments, dup_pairs = build()
    write(customers, subs, invoices, payments, out)
    n_inv = sum(1 for r in invoices if r["type"] == "INV")
    n_crn = len(invoices) - n_inv
    print(f"customers {len(customers)} (incl. {len(dup_pairs)} duplicates), subscriptions {len(subs)}, "
          f"invoices {n_inv}, credit notes {n_crn}, payments {len(payments)}")
    print(f"written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
