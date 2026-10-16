# Go/no-go recommendation: billing data

| | |
|---|---|
| Document ID | BPM-DW-10 |
| Programme | Billing Platform Migration (BPM), data workstream |
| Client | Northstar Systems, Inc. (fictional) |
| Version | 1.0 |
| Date | 2026-10-14 |
| Author (role) | Senior Technical Business Analyst, data workstream lead |
| For | Programme go/no-go, 2026-10-20, chaired by Marcus Oyelaran |
| Status | Issued |

> Fictional client; generated extract. Evidence for every line below is in `results/mock2/` and the documents referenced.

## Recommendation

**Go for 31 October, on two conditions.**

1. Build 1.2 fixes DEF-BPM-007, and the dress rehearsal on 24 October passes all 37 reconciliation checks on a fresh extract.
2. The rehearsal shows the data steps (runbook steps 3 to 9) finish within the planned 6 hours 45 minutes, so gate 4 is passed by 13:00 on the night.

If either condition is not met at the rehearsal, the recommendation becomes no-go for October, and the next window is the November month-end. I would not load payments with the wrong dates and correct them afterwards. Cash by period is one of the figures the Controller signs, and loading something we already know is wrong would turn a sign-off into an argument.

## Criteria and evidence

Three criteria are not met today (GC-04, GC-05, GC-06). All three trace to one defect, DEF-BPM-007, and condition 1 covers them. GC-08 waits for the rehearsal (condition 2).

| ID | Criterion | Mock 2 | Status |
|---|---|---|---|
| GC-01 | All L1 completeness checks pass | 6 of 6 | Met |
| GC-02 | All L2 control totals pass, or every difference traces to an open defect with an agreed fix | 9 of 10; RC-L2-09 differs because of DEF-BPM-007, fix due in build 1.2 | Met; fix verified by condition 1 |
| GC-03 | No L3 difference on any money field; other differences trace to an open defect | 0 money differences; 1,463 paid_date differences, all DEF-BPM-007 | Met; fix verified by condition 1 |
| GC-04 | All integrity checks pass | 10 of 11; RC-RI-11 finds 34 payments dated 1 October (DEF-BPM-007) | Not met: condition 1 |
| GC-05 | Receivables, aging, customer balances, billing and cash for the extract month match exactly | Receivables, aging, balances and September billing match to the cent; September cash differs in all four currencies (DEF-BPM-007) | Not met: condition 1 |
| GC-06 | No open Critical or High defect | DEF-BPM-001 to 006 closed; DEF-BPM-007 is High and open | Not met: condition 1 |
| GC-07 | Every accepted exception has an owner and the Controller's approval | EX-01 to EX-04 approved by Robert Chen on 13 October | Met |
| GC-08 | Data steps rehearsed end to end on a fresh extract | Dress rehearsal on 24 October | Not yet: condition 2 |

## Why this is a reasonable bet

The trend between the mocks is the clearest evidence. Mock 1 passed 13 of 36 checks and found six defects, two of them Critical. Mock 2 passed 33 of 37 and closed all six. Its only failures come from one defect with a known cause, a small and specific fix, and a list of every affected record. Nothing out of scope has been loaded in either mock, and in mock 2 every bridge balances and every in-scope record loaded exactly once.

DEF-BPM-007 changes no amount, currency or link. The fix repeats a change the Platform team has already made and proven once, for invoices in build 1.1.

The honest weak point is that mock 1 had the evidence for this defect and it was missed (`06_mock1_reconciliation_report.md`). The checks that found it in mock 2 stay in place for the rehearsal and the cutover.

## What could still go wrong

| Risk | Likelihood | What we would see | Response |
|---|---|---|---|
| Build 1.2 fixes payment dates but breaks something else | Low | A check failing at the rehearsal | Condition 1: no-go for October |
| The final extract brings values the maps don't cover (a new plan code, status or spelling of a country) | Medium | DQ-03, DQ-10 or DQ-20 failing at gate 1 | Map update on the night, signed by Grace Okafor; 30 minutes allowed in the runbook (step 5) |
| October data has a problem the September extract didn't | Medium | A High or Medium DQ count moving more than 10% | Look at it before loading. The mocks used the same extract on purpose, so this is the one place a newer extract can surprise us. |
| The reconciliation and the loader misread the same rule the same way | Low | Nothing at L1 to L4; integrity checks might still show it | Every rule was walked through with Finance or Billing Ops before either side built it, and Billing Ops walks through 25 customers at gate 4 |
| Customers with no email miss their November invoice | Medium | Billing Ops can't send to 25 customers | EX-03: Billing Ops sends those by hand until the backfill is done |

## Sign-off

| Name | Role | Decision |
|---|---|---|
| Robert Chen | Controller, Finance | Agreed the recommendation and conditions, 2026-10-14 |
| Grace Okafor | Billing Operations Manager | Agreed, 2026-10-14 |
| Tomasz Nowak | Engineering Manager, Platform | Agreed; build 1.2 committed for 2026-10-21 |
| Marcus Oyelaran | Director, PMO | Decision at the programme go/no-go, 2026-10-20 |
