# Data quality rules

| | |
|---|---|
| Document ID | BPM-DW-04 |
| Programme | Billing Platform Migration (BPM), data workstream |
| Client | Northstar Systems, Inc. (fictional) |
| Version | 1.2 |
| Date | 2026-10-13 |
| Author (role) | Senior Technical Business Analyst, data workstream lead |
| Reviewed by | Grace Okafor, Billing Operations Manager |
| Status | Baselined |

> Fictional client; generated extract. The rules are implemented in `recon/sql/05_dq_rules.sql`; results for the mock extract are in `results/profiling/dq_results.csv` and every failing record is in `dq_detail.csv`.

## When the rules run

1. During profiling, to find the problems (`02_data_profiling_report.md`).
2. At the start of every mock and of the dress rehearsal, on whatever extract that run uses.
3. At cutover, as gate 1 in the runbook (`09_cutover_runbook.md`), before anything is loaded.

The rules run on the extract, never on the target. Their job is to say what the loader is about to receive.

## Severity

| Severity | Meaning | What happens at a gate |
|---|---|---|
| Blocker | The mapping can't handle it. Loading would put wrong or missing values in a required field. | Any failing row stops the load. |
| High | Records or money would be lost or misstated if the mapping didn't handle it. | Allowed only because a mapping rule handles it. The count must stay within 10% of the mock 2 count, or it is looked at before loading. |
| Medium | An attribute is wrong or missing. Handled by a mapping rule or an accepted exception. | Same 10% tolerance. |
| Low | Format only. | Reported. |
| Info | A count somebody asked to see. | Reported. |

The 10% tolerance exists for the final extract, which will be a month newer than the mock extract. A jump in a High or Medium count means something changed in legacy and someone should know what before the loader runs.

## Catalog

Results are for the 30 September extract used in both mocks.

| Rule | What it checks | Table | Severity | Failing rows | Handling | Refs |
|---|---|---|---|---:|---|---|
| DQ-01 | Customer id padded with spaces | invoices, payments, subscriptions, customers | High | 1,149 | Trim before every join | M-CUS-02, M-PAY-03 |
| DQ-02 | Country not an ISO 3166 alpha-2 code | lb_customers | Medium | 532 | Country map | M-CUS-06 |
| DQ-03 | Country value missing from the country map | lb_customers | Blocker | 0 | Add the value to the map before loading | M-CUS-06 |
| DQ-04 | Customer created date not in YYYY-MM-DD | lb_customers | Low | 225 | Parse MM/DD/YYYY as well | M-CUS-08 |
| DQ-05 | Duplicate customer (same company and email) | lb_customers | High | 27 | Merge to the earliest record | DEC-BPM-003, M-CUS-03 |
| DQ-06 | Contact email missing or invalid | lb_customers | Medium | 27 | Load blank; Billing Ops backfills | DEC-BPM-006, M-CUS-05 |
| DQ-07 | Amount exported with a thousands separator | lb_invoices, lb_payments | Low | 1,001 | Strip the separator | M-INV-08, M-PAY-07 |
| DQ-08 | Gross does not equal net plus tax | lb_invoices | Medium | 124 | Migrate as billed | DEC-BPM-007, M-INV-10 |
| DQ-09 | Plan code not in the plan table | lb_subscriptions | High | 58 | Map to a grandfathered plan | DEC-BPM-004, M-SUB-04 |
| DQ-10 | Plan code missing from the plan map | lb_subscriptions | Blocker | 0 | Add the code to the map before loading | M-SUB-04 |
| DQ-11 | Payment with no matching invoice | lb_payments | High | 23 | Load as unapplied cash | DEC-BPM-008, M-PAY-09 |
| DQ-12 | Credit note stored as a negative invoice | lb_invoices | Info | 635 | Split to credit notes, reverse the sign | M-CRN-02 |
| DQ-13 | Subscription with zero seats | lb_subscriptions | Medium | 6 | Expected platform reject | M-SUB-05 |
| DQ-14 | Payment currency differs from the invoice | lb_payments | High | 0 | None needed | |
| DQ-15 | Invoice currency differs from the customer | lb_invoices | High | 0 | None needed | |
| DQ-16 | Payments exceed the invoice gross | lb_invoices | High | 0 | None needed | |
| DQ-17 | Subscription ends before it starts | lb_subscriptions | Medium | 0 | None needed | |
| DQ-18 | Customer id not in the customer table | invoices, payments, subscriptions | Blocker | 0 | Fix in legacy before loading | |
| DQ-19 | Open invoice older than the 24-month window | lb_invoices | Info | 54 | Migrates under scope rule S2 | DEC-BPM-002 |
| DQ-20 | Status or payment method missing from its value map | customers, subscriptions, invoices, payments | Blocker | 0 | Add the value to the map before loading | M-CUS-09, M-SUB-08, M-INV-13, M-PAY-08 |

DQ-03, DQ-10, DQ-18 and DQ-20 are Blockers because the staging SQL joins on them. A customer id that isn't in the customer table, or a country, plan code, status or payment method that isn't in its map, would drop or blank a record without raising an error. A rule that returns zero today is still worth running on the final extract; that is when a new plan code or a new spelling of Canada would turn up.

## Changes

| Version | Date | Change |
|---|---|---|
| 1.0 | 2026-08-28 | Rules DQ-01 to DQ-17 agreed in the mapping workshops |
| 1.1 | 2026-10-02 | DQ-18 added after Samira Haddad asked how we would know if a join dropped rows. DQ-19 added because Finance wanted the count of old open invoices. |
| 1.2 | 2026-10-13 | DQ-20 added so that a new status or payment method on the final extract stops the load instead of loading blank or defaulting. |
