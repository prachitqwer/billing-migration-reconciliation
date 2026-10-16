# Data profiling report: legacy billing extract

| | |
|---|---|
| Document ID | BPM-DW-02 |
| Programme | Billing Platform Migration (BPM), data workstream |
| Client | Northstar Systems, Inc. (fictional) |
| Version | 2.1 |
| Date | 2026-10-13 |
| Author (role) | Senior Technical Business Analyst, data workstream lead |
| Reviewed by | Grace Okafor, Billing Operations Manager; Samira Haddad, BI Analyst, Finance Systems |
| Status | Final for the mock extract |

> Fictional client; the extract is generated. Every number below comes from `results/profiling/` and can be reproduced with `python scripts/run_mock.py --profile`.

## Revision history

| Version | Date | Change |
|---|---|---|
| 1.0 | 2026-08-21 | Profile of the July extract, used in the mapping workshops |
| 2.0 | 2026-10-02 | Re-run on the September extract used for both mocks. Same findings; the counts below are from this extract. |
| 2.1 | 2026-10-13 | After both mocks: credit note treatment added to finding 10 (DEC-BPM-012); finding 12 records that payment date should have been in mock 1 coverage; note on DQ-14 and DQ-15 added; DQ-20 added to the clean list. |

## What was profiled

The legacy DBA's extract as of 30 September 2026, taken on 1 October. Five tables, delivered as CSV in UTF-8.

| Table | Rows | Notes |
|---|---:|---|
| lb_customers | 1,227 | One row per customer id |
| lb_plans | 10 | Current plans only; retired plans were deleted from this table in 2021 |
| lb_subscriptions | 1,894 | |
| lb_invoices | 33,266 | 32,631 invoices and 635 credit notes in the same table |
| lb_payments | 32,339 | |
| Total | 68,736 | |

Invoices and payments run from 1 October 2023 to 30 September 2026. The legacy system keeps 36 months online.

A few shapes worth knowing before reading the findings:

- Customers: 974 active (A), 22 on billing hold (H), 231 inactive (I). By currency: 857 USD, 149 CAD, 128 GBP, 93 EUR.
- Subscriptions: 1,224 active, 35 on trial, 69 suspended for non-payment, 38 paused, 378 cancelled, 126 expired, 24 pending activation.
- Invoices: 31,103 paid, 650 open, 56 part paid, 501 void, 321 written off.
- Payments: 17,618 by card, 7,814 ACH, 2,300 wire, 1,406 BACS, 1,204 EFT, 1,139 SEPA, 858 cheque.

## Findings

Each finding has a rule in `04_data_quality_rules.md` that now runs before every load, and a handling rule in the mapping spec.

**1. Customer ids padded with spaces (DQ-01: 1,149 rows).** 811 payments and 338 invoices carry the customer id with trailing spaces (`"C100187 "`). An exact join drops them without an error, which is the worst kind of failure in a migration. Handling: trim on every customer id before any join (M-CUS-02, M-SUB-03, M-INV-03, M-CRN-04, M-PAY-03).

**2. Country is free text (DQ-02: 532 customers).** Seven countries are spelt seventeen ways. The US alone appears as US, USA, United States and U.S.; the UK as GB, UK and United Kingdom. Handling: a country map to ISO alpha-2 (M-CUS-06). DQ-03 stops the load if a spelling turns up that the map doesn't cover. It returned zero.

**3. Two date formats in created_on (DQ-04: 225 customers).** Most are YYYY-MM-DD; 225 are MM/DD/YYYY from an old import. Handling: parse both (M-CUS-08). Low risk, but a silent day/month swap would have moved customer anniversaries.

**4. The same customer twice (DQ-05: 27 customers).** 27 customers were keyed a second time by Sales, with the same company and billing email but different capitalisation, a double space or a stray full stop ("ATLAS CONSULTING PLC" next to "Atlas Consulting PLC", "Meridian&nbsp;&nbsp;Freight LLC" next to "Meridian Freight LLC"). Each duplicate has its own subscription, invoices and payments. Handling: merge on company name and email after case-folding and removing punctuation; the earliest created record survives and the other id is kept on it (DEC-BPM-003, M-CUS-03). Billing Ops reviewed all 27 pairs before the rule was agreed.

**5. Contact emails that aren't email addresses (DQ-06: 27 customers).** 9 say "n/a", 7 are blank, 6 have no top-level domain and 5 stop at the @. Handling: load blank rather than invent a placeholder; Billing Ops backfills after go-live (DEC-BPM-006). 25 of the 27 customers are in scope.

**6. Amounts with thousands separators (DQ-07: 1,001 rows).** 691 invoice rows and 310 payment rows have amounts like "1,234.50". Handling: strip the separator before converting (M-INV-08, M-PAY-07). A naive conversion reads "1,234.50" as 1, so this matters more than its Low severity suggests.

**7. Gross a cent away from net plus tax (DQ-08: 124 invoices).** A rounding bug in the legacy invoice template. 80 of these are inside the migration window. Customers were billed and paid the gross. Handling: migrate as billed (DEC-BPM-007, M-INV-10).

**8. Subscriptions on plans that no longer exist (DQ-09: 58 subscriptions).** Two plan codes retired in 2021, LEG-PRO-2019 (30) and LEG-TEAM-2020 (28), are still referenced. 48 of the 58 are in scope. Handling: two grandfathered plans at the legacy price in the new platform (DEC-BPM-004, M-SUB-04).

**9. Payments with no invoice (DQ-11: 23 payments).** 14 quote an invoice number that doesn't exist, 9 quote none. All 23 are inside the window. Handling: load as unapplied cash on the customer; AR works the list (DEC-BPM-008, M-PAY-09).

**10. Credit notes stored as negative invoices (DQ-12: 635 rows).** The platform has a separate credit note object with positive amounts. Handling: split CRN rows out and reverse the sign (M-CRN-02 to M-CRN-09). This is the one structural difference between the two systems: one legacy table becomes two target tables, so every count bridge has to account for it. Finance confirmed that legacy refunded every credit note through Accounts Payable when it was issued, so a migrated credit note carries no open balance (DEC-BPM-012).

**11. Subscriptions with zero seats (DQ-13: 6 subscriptions).** All six are cancelled subscriptions from late 2024 that were never billed. The platform rejects a quantity below 1. Handling: let the platform reject them and count them as expected rejects; Billing Ops confirmed nobody needs them.

**12. Time stamps are New York local time.** The values are correct; the risk is in how they get converted. 261 invoices and 2,036 payments were recorded late enough in the evening that their date changes if anyone converts the time stamp to UTC. Handling: dates migrate as the New York calendar date with no conversion (DEC-BPM-009). Invoice date went into field-level reconciliation from mock 1 because of this finding. Payment date should have gone in too, and didn't until mock 2 (see DEF-BPM-007 in `07_defect_log.md`).

**13. Old invoices that are still open (DQ-19: 54 invoices).** Older than the 24-month window but still owed. Handling: they migrate (scope rule S2); without them the receivables would be wrong.

## What came back clean

These rules returned zero on the mock extract. They're listed because they were the ones Finance asked about first.

| Rule | Check | Result |
|---|---|---|
| DQ-03 | Country value missing from the country map | 0 |
| DQ-10 | Plan code missing from the plan map | 0 |
| DQ-14 | Payment currency differs from the invoice | 0 |
| DQ-15 | Invoice currency differs from the customer | 0 |
| DQ-16 | Payments exceed the invoice gross | 0 |
| DQ-17 | Subscription ends before it starts | 0 |
| DQ-18 | Child record whose customer id is not in the customer table | 0 |
| DQ-20 | Status or payment method missing from its value map | 0 |

DQ-14 and DQ-15 matter later: because the legacy data has no currency mismatches at all, any mismatch in the target is the loader's doing. That is how DEF-BPM-003 was pinned down in mock 1.
