# Mock cutover 2: reconciliation report

| | |
|---|---|
| Document ID | BPM-DW-08 |
| Programme | Billing Platform Migration (BPM), data workstream |
| Client | Northstar Systems, Inc. (fictional) |
| Version | 1.1 |
| Date | 2026-10-13 |
| Author (role) | Senior Technical Business Analyst, data workstream lead |
| Distribution | Robert Chen, Grace Okafor, Tomasz Nowak, Samira Haddad, Hannah Price, Marcus Oyelaran |
| Status | Final |

> Fictional client; generated extract. Run it yourself with `python scripts/run_mock.py mock2`. Every figure here is in `results/mock2/`.

## Revision history

| Version | Date | Change |
|---|---|---|
| 1.0 | 2026-10-12 | Issued after mock 2 |
| 1.1 | 2026-10-13 | DEF-BPM-007 rated High; exception register approved by Robert Chen and owners named |

## Result

Migration build 1.1, run on 12 October 2026 against the same 30 September extract as mock 1.

**33 of 37 checks passed.** The six mock 1 defects are fixed and retested. The four failures all come from one new High defect, DEF-BPM-007: payment dates converted to UTC.

Mock 2 runs 37 checks where mock 1 ran 36. RC-RI-11, which fails any invoice, credit note or payment dated after the extract date, was added after mock 1 (DEC-BPM-011).

| Level | Checks | Passed | Failed |
|---|---:|---:|---:|
| L1 Completeness | 6 | 6 | 0 |
| L2 Control totals | 10 | 9 | 1 |
| L3 Field level | 5 | 4 | 1 |
| RI Integrity | 11 | 10 | 1 |
| L4 Finance views | 5 | 4 | 1 |

| Mock 1 | Mock 2 |
|---|---|
| 13 of 36 passed, 21 failed, 2 no data | 33 of 37 passed, 4 failed |

## Completeness

Every in-scope record loaded exactly once and nothing else did. Every bridge balances.

| Entity | Legacy rows | Merged | Out of scope | Expected rejects | Loaded | Missing | Not expected |
|---|---:|---:|---:|---:|---:|---:|---:|
| customers | 1,227 | 27 | 47 | 0 | 1,153 | 0 | 0 |
| subscriptions | 1,894 | 0 | 166 | 6 | 1,722 | 0 | 0 |
| invoices | 32,631 | 0 | 9,053 | 0 | 23,578 | 0 | 0 |
| credit notes | 635 | 0 | 191 | 0 | 444 | 0 | 0 |
| payments | 32,339 | 0 | 9,167 | 0 | 23,172 | 0 | 0 |

The four legacy tables that migrate hold 68,726 rows (the 10-row plan table is reference data and isn't migrated). They account for 50,069 loaded records, 27 merged duplicates, 6 expected rejects and 18,624 records out of scope: mostly history older than the 24-month window, plus 24 pending subscriptions that Sales will re-create (DEC-BPM-005).

## The numbers Finance signs

Open receivables match to the cent in every currency.

| Currency | Expected | Loaded | Difference |
|---|---:|---:|---:|
| USD | 228,757.51 | 228,757.51 | 0.00 |
| CAD | 331,093.70 | 331,093.70 | 0.00 |
| GBP | 99,317.02 | 99,317.02 | 0.00 |
| EUR | 43,081.77 | 43,081.77 | 0.00 |

The aging matches in all 20 currency and bucket cuts, and all 459 customer balances match. Net billing for September (invoices that aren't void, less credit notes) matches in every currency: 706,311.22 USD, 208,861.56 CAD, 192,203.78 GBP and 69,817.97 EUR. Credit notes carry no balance, because legacy refunded each one through AP when it was issued (DEC-BPM-012).

Cash received in September does not match:

| Currency | Legacy, September | Loaded as September | Difference |
|---|---:|---:|---:|
| USD | 891,453.69 | 879,788.17 | -11,665.52 |
| CAD | 217,300.20 | 217,049.57 | -250.63 |
| GBP | 165,793.68 | 167,818.64 | 2,024.96 |
| EUR | 76,911.74 | 59,957.08 | -16,954.66 |

None of that money is missing. Payments received on the evening of 30 September were loaded as 1 October, and a few from the evening of 31 August were loaded as 1 September, which is why GBP goes up. That is DEF-BPM-007.

## Retest of the mock 1 defects

| Defect | Evidence in mock 1 | Mock 2 |
|---|---|---|
| DEF-BPM-001 invoice dates | 197 invoice dates a day late | 0 differences on invoice_date |
| DEF-BPM-002 subscription status | 105 suspended or paused loaded as active | 0 differences on status; 69 past_due and 38 paused as expected |
| DEF-BPM-003 payment currency | 7,176 payments loaded as USD | 0 differences on currency; RC-RI-09 passes |
| DEF-BPM-004 merged customers | 24 subscriptions missing, 419 invoices unlinked | RC-L1-02 passes; 0 differences on invoice subscription |
| DEF-BPM-005 tax recalculated | 1,192 tax and 1,267 totals different | 0 differences on tax and total; RC-RI-10 passes |
| DEF-BPM-006 credit notes | 444 loaded as invoices | 444 credit notes loaded; 0 field differences |

All six were closed on 12 October.

## The new defect

DEF-BPM-007: 1,463 payments carry a `paid_date` one day after legacy. All were recorded between 7 p.m. and midnight New York time. 137 changed month, and 34 moved from 30 September into October. Amounts, currencies, customers and invoice links are all correct, which is why receivables and balances still match.

It has the same root cause as DEF-BPM-001: build 1.1 fixed the invoice import and not the payment import. It shows up in four checks.

| Check | Mock 2 result |
|---|---|
| RC-L3-05 payments field level | 1,463 differences, all on paid_date |
| RC-RI-11 no transaction dated after the extract date | 34 payments dated 1 October |
| RC-L2-09 payments by currency and month | 75 of 100 currency-month cuts differ. The workbook lists count and amount as separate rows, so it shows 139 differing rows out of 200. |
| RC-L4-05 cash received in September | different in all four currencies |

It was there in mock 1 as well, and mock 1's output showed it: an October cut in RC-L2-09 that was filed under DEF-BPM-003 without being read. `06_mock1_reconciliation_report.md` and the defect log say how that happened. Mock 2 found it because payment date is now in field-level coverage and RC-RI-11 exists (DEC-BPM-011).

Fix due in build 1.2 on 21 October; full retest at the dress rehearsal on 24 October.

## Transformations Finance should know about

These are built into the expected target, so they don't show as differences. They are listed so nobody is surprised by them after go-live.

| What changed | Records | Rule |
|---|---:|---|
| Duplicate customers merged into the earliest record; the other id kept on the survivor | 27 | DEC-BPM-003, M-CUS-03 |
| Credit notes moved out of the invoice table, sign reversed, no open balance | 444 | M-CRN-02 to M-CRN-09, DEC-BPM-012 |
| Subscriptions on retired plans moved to grandfathered plans (25 Legacy Pro, 23 Legacy Team) | 48 | DEC-BPM-004, M-SUB-04 |
| Open invoices older than the window carried over because they are still owed | 54 | Scope S2 |
| Pending activations not migrated; Sales re-creates them | 24 | DEC-BPM-005 |

## Accepted exception register

Legacy data problems the business has chosen to carry over as they are. Each one is built into the expected target and has an owner. Robert Chen approved all four on 13 October 2026 (GC-07).

| ID | Exception | Records | Owner | Action after go-live |
|---|---|---:|---|---|
| EX-01 | Payments with no matching invoice, loaded as unapplied cash: 17 USD (77,350.24), 3 CAD (19,357.67), 2 GBP (5,784.11), 1 EUR (6,007.74) | 23 | Hannah Price, Accounts Receivable Lead | Apply to the right invoice or refund within 60 days |
| EX-02 | Invoices billed a cent away from net plus tax, migrated as billed | 80 | Robert Chen | None; customers paid what they were billed |
| EX-03 | Customers loaded with no contact email | 25 | Grace Okafor | Backfill within 30 days; Billing Ops sends their November invoices by hand until then |
| EX-04 | Zero-seat cancelled subscriptions rejected by the platform | 6 | Grace Okafor | None; they stay in the legacy archive |

The in-scope records for each exception are listed in `results/mock2/accepted_exceptions.csv` and on the "Accepted exceptions" sheet of the workbook.

## Next

| # | Action | Owner | Due |
|---|---|---|---|
| 1 | Build 1.2 with the DEF-BPM-007 fix | Tomasz Nowak | 2026-10-21 |
| 2 | Data go/no-go recommendation | Data workstream | 2026-10-14 |
| 3 | Programme go/no-go | Marcus Oyelaran | 2026-10-20 |
| 4 | Dress rehearsal on a fresh extract with build 1.2, full reconciliation, timed | Data workstream, Platform | 2026-10-24 |
