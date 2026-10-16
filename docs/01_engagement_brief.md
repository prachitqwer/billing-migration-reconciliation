# Engagement brief: billing migration, data workstream

| | |
|---|---|
| Document ID | BPM-DW-01 |
| Programme | Billing Platform Migration (BPM) |
| Client | Northstar Systems, Inc. (fictional) |
| Version | 1.1 |
| Date | 2026-10-14 |
| Author (role) | Senior Technical Business Analyst, data workstream lead |
| Reviewed by | Marcus Oyelaran, Director, PMO (programme manager) |
| Status | Current |

> Northstar Systems, its people and its customers are fictional, and the legacy extract is generated (`scripts/generate_legacy_extract.py`). The mapping, SQL, reconciliation runs and results in this repository are real and can be re-run.

## Revision history

| Version | Date | Change |
|---|---|---|
| 1.0 | 2026-08-07 | Issued at the start of the data workstream |
| 1.1 | 2026-10-14 | Timeline updated with both mocks and the recommendation; Accounts Receivable added to the stakeholders |

## Why this work exists

Northstar bills about a thousand live customers in four currencies from a billing system it built in-house in 2014. Finance has been working around it for years: credit notes live in the invoice table as negative invoices, the same customer can exist twice, and country is free text. The company is moving to a subscription billing platform, and the target is for every renewal from 1 November onward to bill from the new platform.

That makes the cutover weekend 31 October to 1 November 2026.

The data workstream exists to answer one question for the Controller before that weekend: if we switch, will the new platform owe, be owed and have billed exactly what the old one says? Everything in this repository is the evidence for that answer.

## What the data workstream delivers

| # | Deliverable | Document |
|---|---|---|
| 1 | Profile of the legacy data and the problems in it | `02_data_profiling_report.md` |
| 2 | Source-to-target mapping, scope rules and value maps | `03_source_to_target_mapping.md` / `.xlsx` |
| 3 | Data quality rules that run before every load | `04_data_quality_rules.md` |
| 4 | Reconciliation approach, checks and go/no-go criteria | `05_reconciliation_strategy.md` |
| 5 | Reconciliation of each mock cutover | `06_mock1_reconciliation_report.md`, `08_mock2_reconciliation_report.md` |
| 6 | Defects raised against the migration build | `07_defect_log.md` |
| 7 | Data steps of the cutover runbook | `09_cutover_runbook.md` |
| 8 | Go/no-go recommendation for the data | `10_go_no_go_recommendation.md` |
| 9 | Decisions taken along the way | `11_decision_log.md` |

## Scope

In scope: customers, subscriptions, invoices, credit notes and payments, for 24 months of history plus anything still owed (DEC-BPM-002).

Out of scope, owned elsewhere in the programme:

- The plan catalogue and price lists in the new platform (configuration workstream). The data workstream only maps legacy plan codes onto it.
- The payment gateway switch and the general ledger feed (integrations workstream).
- Testing that billing works after the load: renewals, dunning, invoice PDFs (QA, Lena Fischer).
- The read-only legacy archive that keeps the older history (Platform team).

## Who is involved

| Name | Role | On this workstream |
|---|---|---|
| Robert Chen | Controller, Finance | Accountable for the financial data. Signs off control totals, receivables, billing and cash. Approves accepted exceptions. |
| Hannah Price | Accounts Receivable Lead | Owns the unapplied cash list (EX-01) after go-live. |
| Grace Okafor | Billing Operations Manager | SME for customers, subscriptions and statuses. Owns data clean-up in legacy and the email backfill after go-live. |
| Tomasz Nowak | Engineering Manager, Platform | Owns the migration loader and its fixes. |
| Samira Haddad | BI Analyst, Finance Systems | Reviews the control totals; owns the receivables reports after go-live. |
| Ingrid Halvorsen | Information Security Manager | Approved how the customer extract is handled in the migration environment. |
| Lena Fischer | QA Manager | Consulted on the overlap between reconciliation and billing UAT. |
| Marcus Oyelaran | Director, PMO | Programme manager. Chairs go/no-go. |
| Senior Technical Business Analyst | Data workstream lead | Mapping, data quality rules, reconciliation, mock reports, recommendation. |

The split that mattered most: the Platform team builds the loader, the data workstream proves what it loaded. The reconciliation never reuses loader code or loader logs (DEC-BPM-001).

## Timeline

| Date | Milestone | Status |
|---|---|---|
| 2026-08-03 | Data workstream starts; first extract requested | Done |
| 2026-08-10 to 09-04 | Profiling on the July extract; mapping workshops with Finance and Billing Ops | Done |
| 2026-09-18 | Mapping spec 1.0 baselined | Done |
| 2026-10-01 | September extract (as of 30 Sep) taken for both mocks | Done |
| 2026-10-02 | Migration build 1.0 delivered | Done |
| 2026-10-05 | Mock cutover 1 | Done: 13 of 36 checks passed, 6 defects |
| 2026-10-09 | Migration build 1.1 delivered | Done |
| 2026-10-12 | Mock cutover 2 | Done: 33 of 37 checks passed, 1 new defect |
| 2026-10-14 | Data go/no-go recommendation issued | Done |
| 2026-10-20 | Programme go/no-go meeting | Scheduled |
| 2026-10-24 | Dress rehearsal on a fresh extract, build 1.2 | Planned |
| 2026-10-31 to 11-01 | Production cutover | Planned |

Both mocks used the same September extract on purpose, so any change in the results came from the build and not from the data.

## Assumptions and constraints

- The legacy system is frozen for the cutover window. Nothing is keyed after the final extract is taken.
- Legacy timestamps are New York local time. The platform stores business dates. No time zone conversion is wanted (DEC-BPM-009).
- Control totals have zero tolerance (DEC-BPM-010). Billing data that is a cent out gets a reason, not a rounding allowance.
- In the scenario, the customer extract never leaves the migration environment.
