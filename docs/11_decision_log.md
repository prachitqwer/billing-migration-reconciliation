# Decision log: data workstream

| | |
|---|---|
| Document ID | BPM-DW-11 |
| Programme | Billing Platform Migration (BPM), data workstream |
| Client | Northstar Systems, Inc. (fictional) |
| Version | 1.5 |
| Date | 2026-10-08 |
| Author (role) | Senior Technical Business Analyst, data workstream lead |
| Status | Live |

> Fictional client. Decisions are recorded when they are made, with the options that were turned down.

| ID | Date | Decision | Options considered | Decided by | Why |
|---|---|---|---|---|---|
| DEC-BPM-001 | 2026-08-12 | Reconcile against an expected target built independently from the mapping spec. Never reuse the loader's code or logs. | Reconcile from the loader's own load report; sample-based checks | Robert Chen, Tomasz Nowak | A loader checking itself repeats its own mistakes. Platform agreed to store legacy keys on every record so matching never depends on platform ids. |
| DEC-BPM-002 | 2026-08-19 | Migrate 24 months of history (from 2024-10-01) plus anything still owed. Older history goes to a read-only legacy archive. | All 36 months online; open items only | Robert Chen | Covers two audit years and every open balance. Open items only would have lost the payment history behind customer disputes. |
| DEC-BPM-003 | 2026-08-26 | Merge duplicate customers that share company name and email after case-folding and removing punctuation. The earliest created record survives; children move to it; the other id is kept on it. A merged customer takes the strongest status in its group (hold, then active, then inactive). | Migrate duplicates and merge later in the platform; match on name only | Grace Okafor | Billing Ops checked every pair by hand. Name-only matching would pair different companies that share a trading name. Merging later would have meant two live accounts billing one customer in November. |
| DEC-BPM-004 | 2026-08-26 | Subscriptions on the two retired plan codes move to two grandfathered plans in the platform, at the legacy price. | Move them to the current Professional and Business plans | Grace Okafor, Product (configuration workstream) | Moving 48 customers onto current prices during a system change is a pricing decision, not a migration one. |
| DEC-BPM-005 | 2026-09-02 | Pending activations (PEND) are not migrated. Sales re-creates them in the platform. | Migrate as trialing | Grace Okafor, Sales Operations | They have never billed. Sales wanted them on the new order form anyway, with each start date confirmed again with the customer. |
| DEC-BPM-006 | 2026-09-02 | Invalid or missing contact emails load blank. Billing Ops backfills within 30 days of go-live. No placeholder addresses. | Generated placeholder addresses; block the customer | Grace Okafor, Ingrid Halvorsen | A placeholder address would have the platform emailing invoices into a void, or to a domain we don't own. |
| DEC-BPM-007 | 2026-09-09 | Invoices migrate as billed: tax and gross imported from legacy, not recalculated, including the invoices billed a cent away from net plus tax. | Recalculate in the platform; correct the one-cent invoices | Robert Chen | The invoice the customer received and paid is the record. Correcting it would create one-cent balances on paid invoices. |
| DEC-BPM-008 | 2026-09-09 | Payments with no matching invoice load as unapplied cash on the customer. AR works the list after go-live. | Leave them in legacy; force-match by amount | Robert Chen | The cash was received and has to be on the customer's account. Matching by amount alone picks the wrong invoice whenever a customer has several invoices of the same value, which monthly subscribers always do. |
| DEC-BPM-009 | 2026-09-16 | Dates migrate as the New York calendar date of the legacy time stamp. No time zone conversion anywhere. | Convert to UTC and store time stamps | Robert Chen, Tomasz Nowak | Finance closes on New York business days, and profiling of the July extract showed hundreds of evening time stamps whose date would change in UTC. |
| DEC-BPM-010 | 2026-09-16 | Zero tolerance on control totals. A one-cent difference fails. | Tolerance of 0.01% of value | Robert Chen | A percentage tolerance on 17 million USD hides real errors. Known one-cent legacy variances are carried in the expected target instead. |
| DEC-BPM-011 | 2026-10-07 | From mock 2, field-level coverage adds payment date, payment method and customer created date, and a new check, RC-RI-11, fails any invoice, credit note or payment dated after the extract date. | Keep mock 1 coverage | Data workstream, agreed by Robert Chen | DEF-BPM-001 showed the loader converting time stamps. Payment date had been left out of mock 1 coverage, and its month-level check was failing for a different reason (DEF-BPM-003), so nothing was watching payment dates. Eight invoices dated October in a September extract had been the tell for DEF-BPM-001; RC-RI-11 makes that a check of its own. |
| DEC-BPM-012 | 2026-10-08 | Credit notes migrate as history with no open balance and stay out of the receivables and balance views. | Load them as open customer credit | Robert Chen | Legacy refunded every credit note through Accounts Payable when it was issued; the refund sits in the AP ledger, not in billing. Loading them as open credit would pay customers twice. Raised by Samira Haddad during mock 1 triage. |

## Changes

| Version | Date | Change |
|---|---|---|
| 1.0 | 2026-08-26 | DEC-BPM-001 to 004 |
| 1.1 | 2026-09-02 | DEC-BPM-005 and 006 |
| 1.2 | 2026-09-09 | DEC-BPM-007 and 008 |
| 1.3 | 2026-09-16 | DEC-BPM-009 and 010 |
| 1.4 | 2026-10-07 | DEC-BPM-011 |
| 1.5 | 2026-10-08 | DEC-BPM-012 |
