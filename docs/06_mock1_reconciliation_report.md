# Mock cutover 1: reconciliation report

| | |
|---|---|
| Document ID | BPM-DW-06 |
| Programme | Billing Platform Migration (BPM), data workstream |
| Client | Northstar Systems, Inc. (fictional) |
| Version | 1.1 |
| Date | 2026-10-13 |
| Author (role) | Senior Technical Business Analyst, data workstream lead |
| Distribution | Robert Chen, Grace Okafor, Tomasz Nowak, Samira Haddad, Marcus Oyelaran |
| Status | Final |

> Fictional client; generated extract. Run it yourself with `python scripts/run_mock.py mock1`. Every figure here is in `results/mock1/`. The results are regenerated with the current reconciliation. RC-RI-11 is left out of mock 1 because it was added afterwards and would change the result; the other later additions (DQ-20, the accepted exceptions output, the loaded-twice test in L1) change none of mock 1's numbers.

## Revision history

| Version | Date | Change |
|---|---|---|
| 1.0 | 2026-10-06 | Issued after mock 1 |
| 1.1 | 2026-10-13 | "What this run showed that we missed" added after mock 2 found DEF-BPM-007; action status updated |

## Result

Migration build 1.0, run on 5 October 2026 against the 30 September extract.

**13 of 36 checks passed, 21 failed, and 2 had nothing to compare.** Six defects were raised, two of them Critical. Mock 1 is not a basis for go-live, and nobody expected it to be: this was the first time the loader had run against a full extract.

| Level | Checks | Passed | Failed | No data |
|---|---:|---:|---:|---:|
| L1 Completeness | 6 | 3 | 3 | 0 |
| L2 Control totals | 10 | 2 | 8 | 0 |
| L3 Field level | 5 | 1 | 3 | 1 |
| RI Integrity | 10 | 7 | 2 | 1 |
| L4 Finance views | 5 | 0 | 5 | 0 |

The two "no data" checks are RC-L3-04 and RC-RI-04, the credit note checks. They had nothing to compare because no credit notes loaded (DEF-BPM-006). The reconciliation reports a check that compared nothing as NO DATA rather than PASS; an empty table proves nothing.

## What the Controller would have seen on Monday morning

Open receivables, expected against what build 1.0 loaded:

| Currency | Expected | Loaded | Difference |
|---|---:|---:|---:|
| USD | 228,757.51 | 353.57 | -228,403.94 |
| CAD | 331,093.70 | 293,798.71 | -37,294.99 |
| GBP | 99,317.02 | 88,680.41 | -10,636.61 |
| EUR | 43,081.77 | 42,643.79 | -437.98 |

USD receivables almost disappeared. Two defects stack up there: 444 credit notes loaded as open invoices with negative balances (DEF-BPM-006), and every unapplied payment was loaded in USD whatever its real currency (DEF-BPM-003). Of 630 customer balances, 360 were wrong.

September cash received, which Finance closes from legacy:

| Currency | Expected | Loaded |
|---|---:|---:|
| USD | 891,453.69 | 1,324,613.46 |
| CAD | 217,300.20 | 0.00 |
| GBP | 165,793.68 | 0.00 |
| EUR | 76,911.74 | 0.00 |

Every CAD, GBP and EUR payment came through as USD.

## The completeness bridge

| Entity | Legacy rows | Merged | Out of scope | Expected rejects | Expected loads | Actual loads | Missing | Not expected |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| customers | 1,227 | 27 | 47 | 0 | 1,153 | 1,153 | 0 | 0 |
| subscriptions | 1,894 | 0 | 166 | 6 | 1,722 | 1,698 | 24 | 0 |
| invoices | 32,631 | 0 | 9,053 | 0 | 23,578 | 24,022 | 0 | 444 |
| credit notes | 635 | 0 | 191 | 0 | 444 | 0 | 444 | 0 |
| payments | 32,339 | 0 | 9,167 | 0 | 23,172 | 23,172 | 0 | 0 |

Customers and payments were complete. The six zero-seat subscriptions were rejected by the platform exactly as expected (RC-L1-03 passed). The 444 "not expected" invoices are the 444 missing credit notes; the key-level comparison shows they are the same CRN numbers.

## How each failure traced to a defect

Each defect below was raised with the failing checks and the record list from `l3_field_differences.csv` or `l1_key_differences.csv` attached. Detail, root cause and fix are in `07_defect_log.md`.

**DEF-BPM-003, payment currency (Critical).** RC-RI-09 found 7,170 applied payments whose currency didn't match their invoice. Profiling had shown zero such payments in legacy (DQ-14), so the mismatch was created by the load. L3 showed the field: 7,176 payments had currency USD instead of CAD (2,951), GBP (2,440) or EUR (1,785). The extra six are unapplied payments, which have no invoice to mismatch against. That also explains RC-L2-09, RC-L2-10 and RC-L4-05 failing in every non-USD cut.

**DEF-BPM-002, subscription status (Critical).** RC-L2-03 showed no past_due and no paused subscriptions at all. RC-L3-02 listed them: 67 suspended subscriptions and 38 paused ones loaded as active. In production, the 67 would have regained access and the 38 would have started billing again on 1 November.

**DEF-BPM-006, credit notes (High).** RC-L1-05 found all 444 credit notes missing, and RC-L1-04 found the same 444 numbers in the invoice table. RC-RI-10 flagged them as invoices with a negative total, status open.

**DEF-BPM-004, merged customers (High).** RC-L1-02 found 24 subscriptions missing. All 24 belong to the duplicate customers merged under DEC-BPM-003; 20 of them are active. RC-L3-03 then showed 419 invoices for those subscriptions loaded with no subscription link. The invoices and payments themselves had moved to the surviving customer correctly, which is why no invoice or payment went missing and the customer checks passed.

**DEF-BPM-005, tax recalculated (High).** RC-L3-03 found 1,192 invoices with tax one cent away from legacy. Most were in New York (379), Texas (238), Washington (199) and North Carolina (146), where the rate regularly lands on an exact half cent; legacy always rounded that up and the platform didn't. It also found 1,267 totals that differed. That is 1,190 of the 1,192 (in the other two the recalculated cent happened to cancel a legacy one-cent variance), plus 77 of the 80 invoices that legacy had billed a cent off (DQ-08). The platform had quietly "fixed" those to net plus tax, which is exactly what DEC-BPM-007 says not to do. Because the paid amount came from the real payments, 1,163 invoices ended up showing more paid than billed (RC-RI-10).

**DEF-BPM-001, invoice dates (High).** RC-L3-03 found 197 invoices dated a day late. All were raised after 7 p.m. New York time in winter or 8 p.m. in summer; the loader had converted the time stamp to UTC before taking the date. 144 of the 197 moved into the next month, and 8 moved from 30 September into October, a month that hasn't happened yet in this extract. RC-L2-05 showed those as invoice cuts for "USD 2026-10" and "EUR 2026-10" that legacy doesn't have.

## What passed, and why that matters

Customers were clean at every level: count, status, country, currency and all seven fields in coverage. That covers the trimming, the country map and the duplicate merge, all of which were profiling findings. Payments were complete and linked to the right invoices and customers, and every payment amount matched to the cent; only the currency label was wrong. Nothing out of scope was loaded. The records that went missing (24 subscriptions, 444 credit notes) were lost in the merge and routing steps, not in the scope rules.

## What this run showed that we missed

Payment dates were wrong in mock 1 too (DEF-BPM-007), and the output said so. RC-L2-09, payments by currency and month, had a cut for "USD 2026-10": 34 payments and 85,464.77 in an extract taken as of 30 September. And in RC-L4-05, the raw September cash amounts added up across all four currencies came to 26,845.85 less than legacy, which a currency relabel on its own can't explain.

Both checks were failing in every cut because of the currency defect, and both were filed under DEF-BPM-003 without reading the individual cuts. Payment date wasn't in L3 coverage either. That was a judgement made before mock 1, and with profiling finding 12 in hand it was the wrong one.

DEF-BPM-001's diagnosis made the gap obvious. From mock 2, every date the loader writes is in L3 coverage, and a new check, RC-RI-11, fails any invoice, credit note or payment dated after the extract date (DEC-BPM-011). We didn't run those new checks against mock 1's load files on 7 October. That would have caught DEF-BPM-007 in time for build 1.1; instead mock 2 found it, both ways. The lessons are in the strategy: when a check fails for a known reason, read its failing lines anyway, and when a check is added, run the previous mock's load files through it the same day.

## Actions

| # | Action | Owner | Due | Status |
|---|---|---|---|---|
| 1 | Fix DEF-BPM-001 to 006 in build 1.1 | Tomasz Nowak | 2026-10-09 | Done |
| 2 | Re-baseline the loader's value maps from `config/value_maps/` rather than its own copy | Tomasz Nowak | 2026-10-09 | Done |
| 3 | Add payment date, payment method and customer created date to L3 coverage, and add RC-RI-11 | Data workstream | 2026-10-07 | Done |
| 4 | Make "no time zone conversion" explicit in M-INV-05, M-CRN-05 and M-PAY-05 | Data workstream | 2026-10-06 | Done (mapping 1.1) |
| 5 | Run mock 2 on the same extract | Data workstream | 2026-10-12 | Done |
