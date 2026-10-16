# Cutover runbook: data steps

| | |
|---|---|
| Document ID | BPM-DW-09 |
| Programme | Billing Platform Migration (BPM), data workstream |
| Client | Northstar Systems, Inc. (fictional) |
| Version | 0.9 |
| Date | 2026-10-14 |
| Author (role) | Senior Technical Business Analyst, data workstream lead |
| Reviewed by | Tomasz Nowak (Platform), Grace Okafor (Billing Ops), Robert Chen (Finance) |
| Status | Draft until the dress rehearsal on 2026-10-24; durations below are planned, not measured |

> Fictional client. This covers the data steps only. The payment gateway switch, the general ledger feed and post-load billing tests are in the programme runbook, owned by their workstreams.

## The window

Legacy billing freezes at 06:00 New York time on Saturday 31 October, after Friday night's billing run and the last manual invoices on Friday afternoon. The platform has to be ready for its first billing run, the 1 November renewals, at 02:00 on Sunday. The last point at which the switch can be cancelled with no clean-up is the gateway switch at 16:00 on Saturday (step 12). Everything before that only reads legacy.

## Steps

All times New York, Saturday 31 October unless stated.

| # | Time | Step | Owner | Gate / done when |
|---|---|---|---|---|
| 1 | Fri 17:00 | Billing Ops stops manual invoices and credit notes in legacy | Grace Okafor | Confirmation in the cutover channel |
| 2 | 06:00 | Legacy billing set to read-only; card payments held at the gateway | Platform | Test invoice in legacy fails to save |
| 3 | 06:15 | Final extract taken: five tables, UTF-8 CSV, row counts in the manifest | Legacy DBA | Manifest counts match the tables |
| 4 | 06:45 | Run the data quality rules on the final extract | Data workstream | **Gate 1:** no Blocker rule failing (DQ-03, DQ-10, DQ-18, DQ-20); High and Medium counts within 10% of mock 2 or explained |
| 5 | 07:15 | Value maps updated for any new country, plan, status or method value found in step 4 (30 minutes allowed) | Data workstream | Maps signed by Grace Okafor, or nothing new |
| 6 | 07:45 | Loader build 1.2 run against the final extract | Platform | Load report produced; rejects only from DQ-13 |
| 7 | 10:00 | Full reconciliation, all 37 checks | Data workstream | **Gate 2:** every check passes. Accepted exceptions (EX-01 to 04) are built into the expected target, so they never show as differences; any difference stops the run here. |
| 8 | 11:00 | Finance review of L4: receivables, aging, customer balances, and October billing and cash, all against legacy, which is what Finance will close October from | Robert Chen, Samira Haddad | **Gate 3:** Controller signs the workbook summary |
| 9 | 12:00 | Billing Ops walkthrough of 25 customers picked from the exception and transformation lists (merged, grandfathered, unapplied cash, blank email, suspended) | Grace Okafor | **Gate 4:** no surprises, or each one explained in the channel |
| 10 | 13:00 | Unapplied cash list (EX-01) and blank-email list (EX-03) handed to their owners | Data workstream | Owners confirm receipt |
| 11 | 15:00 | Go/no-go call | Marcus Oyelaran | Decision recorded |
| 12 | 16:00 | Payment gateway and customer portal switched to the platform | Integrations | Point of no return for a clean rollback |
| 13 | Sun 02:00 | First platform billing run (1 November renewals) | Platform | Run completes |
| 14 | Sun 08:00 | Renewal check: count and value of invoices raised against subscriptions due on 1 November | Data workstream, Billing Ops | Matches the expected renewals list built from the loaded subscriptions |
| 15 | Mon 09:00 | Hypercare starts; reconciliation of the first platform-only day | Data workstream | Daily for two weeks |

## When to stop

The data workstream will recommend stopping before step 12 if any of these happen:

- A Blocker data quality rule fails at gate 1 and can't be fixed in the map within the 30 minutes allowed at step 5.
- Any L1 completeness check fails at gate 2.
- Any money difference at L2 or L4 that is not an approved exception.
- The Controller doesn't sign at gate 3.
- Step 7 finishes after 13:00. Gates 3 and 4 need two hours, and the gateway switch can't slip past 16:00 without moving the first billing run.

Stopping before step 12 means lifting legacy out of read-only, releasing the held card payments to legacy and re-running the October cutover plan for the next month-end. Nothing in the platform is used, so nothing needs reversing.

After step 12 there is no clean rollback. Problems are fixed forward in the platform with the reconciliation re-run to prove the fix.

## What the dress rehearsal has to prove

The rehearsal on 24 October runs steps 2 to 9 against a fresh extract in the migration environment, with real timings.

1. Build 1.2 fixes DEF-BPM-007: all 37 checks pass.
2. Steps 3 to 9 fit in the planned 6 hours 45 minutes (06:15 to 13:00), which leaves room before the 16:00 gateway switch.
3. The DQ counts on a newer extract stay within tolerance, so the gate 1 thresholds are realistic.

The measured durations go into version 1.0 of this runbook.
