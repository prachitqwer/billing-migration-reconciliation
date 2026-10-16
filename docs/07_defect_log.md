# Defect log: migration build

| | |
|---|---|
| Document ID | BPM-DW-07 |
| Programme | Billing Platform Migration (BPM), data workstream |
| Client | Northstar Systems, Inc. (fictional) |
| Version | 1.3 |
| Date | 2026-10-13 |
| Author (role) | Senior Technical Business Analyst, data workstream lead |
| Defects owned by | Tomasz Nowak, Engineering Manager, Platform |
| Status | Live |

> Fictional client; generated extract. The loader in `migration/loader.py` reproduces builds 1.0 and 1.1 so each defect can be seen in the results.

## Severity

| Severity | Meaning |
|---|---|
| Critical | Money, currency or a customer-facing state wrong on many records. Billing would do the wrong thing on day one. |
| High | Records missing, or amounts, dates or links wrong, without an immediate customer-facing effect. |
| Medium | An attribute wrong with no amount, date, currency or allocation affected. |
| Low | Cosmetic. |

## Summary

| ID | Title | Severity | Found in | Records | Fixed in | Retest | Status |
|---|---|---|---|---:|---|---|---|
| DEF-BPM-001 | Invoice dates converted to UTC | High | Mock 1 | 197 | 1.1 | Mock 2: 0 differences | Closed |
| DEF-BPM-002 | Suspended and paused subscriptions loaded as active | Critical | Mock 1 | 105 | 1.1 | Mock 2: 0 differences | Closed |
| DEF-BPM-003 | Payment currency not mapped, loaded as USD | Critical | Mock 1 | 7,176 | 1.1 | Mock 2: 0 differences | Closed |
| DEF-BPM-004 | Merge dropped the merged-away customers' subscriptions | High | Mock 1 | 24 subscriptions, 419 invoices | 1.1 | Mock 2: 0 differences | Closed |
| DEF-BPM-005 | Tax recalculated by the platform instead of imported | High | Mock 1 | 1,192 tax, 1,267 totals | 1.1 | Mock 2: 0 differences | Closed |
| DEF-BPM-006 | Credit notes loaded as negative invoices | High | Mock 1 | 444 | 1.1 | Mock 2: 0 differences | Closed |
| DEF-BPM-007 | Payment dates converted to UTC | High | Mock 2 | 1,463 | 1.2 (due 2026-10-21) | Dress rehearsal 2026-10-24 | Open |

## Detail

### DEF-BPM-001 Invoice dates converted to UTC

Evidence: RC-L3-03 found 197 invoices with `invoice_date` one day after legacy. RC-L2-05 showed invoice cuts for October 2026, which legacy doesn't have (7 USD invoices, 1 EUR).

Effect: every affected invoice was raised in the evening, New York time. 144 of the 197 moved into the following month, which would have shifted billed revenue between periods. 8 moved from 30 September into October.

Root cause (Platform): the loader read the legacy time stamp as New York time and passed it to the platform's date import, which normalises to UTC before keeping the date.

Fix: pass the date part of the legacy time stamp only. M-INV-05 was reworded to make "no time zone conversion" explicit (mapping 1.1); the rule itself didn't change (DEC-BPM-009).

### DEF-BPM-002 Suspended and paused subscriptions loaded as active

Evidence: RC-L2-03 showed 0 past_due and 0 paused subscriptions against 69 and 38 expected. RC-L3-02 listed 67 SUSP and 38 PAUS subscriptions loaded as active.

Effect: on 1 November the 38 paused subscriptions would have billed, and the 67 suspended for non-payment would have had access restored.

Root cause (Platform): the loader's status table was copied from mapping draft 0.3, before SUSP and PAUS were agreed in workshop 4. The platform fills a blank status with active rather than rejecting the row.

Fix: the loader now reads `config/value_maps/` directly instead of keeping its own copy. The Platform team also set the platform import to reject a blank status.

### DEF-BPM-003 Payment currency not mapped, loaded as USD

Evidence: RC-RI-09 found 7,170 applied payments in a different currency from their invoice. Profiling found none in legacy (DQ-14), so the load created them. RC-L3-05 found 7,176 payments with currency USD (2,951 CAD, 2,440 GBP and 1,785 EUR in legacy); the extra six are unapplied payments, which have no invoice to mismatch. RC-L2-09, RC-L2-10 and RC-L4-05 failed in every non-USD cut.

Effect: 4,049,985.40 CAD, 2,207,990.65 GBP and 1,493,889.46 EUR of receipts recorded as US dollars. Receivables and cash by currency were wrong for every non-USD customer.

Root cause (Platform): the currency column was left out of the payment mapping in the loader. The platform defaults a payment's currency to the account default, which is USD.

Fix: currency mapped (M-PAY-06).

### DEF-BPM-004 Merge dropped the merged-away customers' subscriptions

Evidence: RC-L1-02 found 24 subscriptions missing, all belonging to duplicate customers merged under DEC-BPM-003 (20 active, 2 suspended, 2 cancelled). RC-L3-03 found the 419 invoices for those subscriptions loaded with no subscription link.

Effect: 20 active subscriptions would not have renewed on the new platform.

Root cause (Platform): the merge step moved invoices and payments to the surviving customer but selected subscriptions on the original customer id, which for a merged-away customer no longer exists.

Fix: subscriptions are re-pointed to the survivor along with the invoices and payments.

### DEF-BPM-005 Tax recalculated by the platform instead of imported

Evidence: RC-L3-03 found tax one cent away from legacy on 1,192 invoices, and a different total on 1,267, including 77 of the 80 invoices billed a cent off in legacy (DQ-08). Amount due differed on 49 invoices (41 open, 8 written off) because their total had changed. RC-L2-07 failed in every currency. RC-RI-10 found 1,163 invoices showing more paid than billed.

Effect: migrated invoices would no longer match the invoices customers received and paid, and over a thousand would have shown a one-cent credit.

Root cause (Platform): migrated invoices went through the platform's tax engine, which recalculated tax from the region rate and rounds half cents differently from legacy.

Fix: migrated invoices are imported with external tax and total as provided (M-INV-09, M-INV-10). Mapping 1.2 rewords both rows to say the platform must not recalculate.

### DEF-BPM-006 Credit notes loaded as negative invoices

Evidence: RC-L1-05 found all 444 in-scope credit notes missing, and RC-L1-04 found the same 444 numbers loaded as invoices. RC-RI-10 flagged 444 invoices with a negative total. RC-L4-01 showed open receivables understated in every currency.

Effect: 197,254.31 USD, 56,652.71 CAD, 16,420.72 GBP and 6,445.75 EUR of credit notes sat in receivables as negative open invoices. Those credit notes were refunded through AP when they were issued (DEC-BPM-012), so in the platform they would have been paid out a second time.

Root cause (Platform): CRN rows were not routed to the credit note import. They went through the invoice mapping, and the unmapped CRN status defaulted to open.

Fix: CRN rows go to the credit note import with the sign reversed (M-CRN-02 to M-CRN-09).

### DEF-BPM-007 Payment dates converted to UTC

Evidence (mock 2): RC-L3-05 found 1,463 payments with `paid_date` one day after legacy. RC-RI-11 found 34 payments dated 1 October in an extract taken as of 30 September. RC-L2-09 showed 75 of 100 currency-month cuts different. RC-L4-05 showed cash for September different in all four currencies (detail in `08_mock2_reconciliation_report.md`).

Effect: no amount, currency or invoice link is wrong. 1,463 payments carry the next day's date; 137 of them change month, and 34 move from 30 September into October. September cash would not agree with legacy, which is what Finance closes from, and days-to-pay figures would be a day out for those customers.

Root cause (Platform): the payment loader uses the same time stamp conversion as the invoice loader. The fix for DEF-BPM-001 in build 1.1 was applied to the invoice import only.

How it was missed in mock 1: payment date was not in mock 1's field-level coverage. The data workstream left it to the month-level check, RC-L2-09, and that was a mistake given profiling finding 12. In mock 1, RC-L2-09 was failing in every cut because of DEF-BPM-003, and the whole check was filed under that defect. The clue was in the output all along: a "USD 2026-10" cut with 34 payments and 85,464.77 in a September extract. Nobody read the individual cuts of a check that was already explained. DEC-BPM-011 is the fix: payment date went into coverage, and RC-RI-11 now fails any invoice, credit note or payment dated after the extract date on its own. Those checks were not run against mock 1's load files when they were added on 7 October; had they been, this defect would have reached the Platform team in time for build 1.1.

Fix: the same change as DEF-BPM-001, applied to the payment import. Platform estimate: build 1.2 on 2026-10-21. Retest: full reconciliation at the dress rehearsal on 2026-10-24.

Severity: High. Dates are wrong, and cash by period is an allocation, so by the definitions above it can't be Medium. No customer would see it on day one, which is why it isn't Critical. It is a go-live condition (`10_go_no_go_recommendation.md`).

## Changes

| Version | Date | Change |
|---|---|---|
| 1.0 | 2026-10-06 | DEF-BPM-001 to 006 raised from mock 1 |
| 1.1 | 2026-10-08 | Root causes added after triage with the Platform team |
| 1.2 | 2026-10-12 | DEF-BPM-001 to 006 retested in mock 2 and closed |
| 1.3 | 2026-10-13 | DEF-BPM-007 raised from mock 2, rated High; how it was missed in mock 1 recorded |
