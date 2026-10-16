-- 02  Expected target: what the new billing platform should hold after the load,
--     built straight from the mapping spec (docs/03) and independent of the loader.
--
-- Keys stay legacy keys so the comparison never depends on the platform's own ids.
-- Money is in integer cents. Parameters come from the params table:
--   cutoff   history window start (DEC-BPM-002)
--   as_of    extract date

-- ---------------------------------------------------------------- scope

DROP TABLE IF EXISTS scope_invoices;
CREATE TABLE scope_invoices AS
SELECT i.inv_no
FROM stg_invoices i, params p
WHERE i.inv_type = 'INV'
  AND (i.inv_date >= p.cutoff OR i.status IN ('OPEN', 'PART'));       -- S2: 24 months, plus anything still owed

DROP TABLE IF EXISTS scope_customers;
CREATE TABLE scope_customers AS
SELECT cust_id FROM stg_survivors WHERE group_status IN ('A', 'H')     -- S1: live customers
UNION
SELECT DISTINCT i.owner FROM stg_invoices i JOIN scope_invoices s USING (inv_no);  -- S1: or billed inside the window

DROP TABLE IF EXISTS scope_subscriptions;
CREATE TABLE scope_subscriptions AS
SELECT s.sub_id
FROM stg_subscriptions s, params p
WHERE s.owner IN (SELECT cust_id FROM scope_customers)
  AND s.status <> 'PEND'                                                -- S3: pending activations stay with Sales (DEC-BPM-005)
  AND (   s.status IN ('ACT', 'TRL', 'SUSP', 'PAUS')
       OR s.end_date >= p.cutoff
       OR s.sub_id IN (SELECT i.sub_id FROM stg_invoices i JOIN scope_invoices USING (inv_no)));

DROP TABLE IF EXISTS scope_credit_notes;
CREATE TABLE scope_credit_notes AS
SELECT inv_no FROM stg_invoices
WHERE inv_type = 'CRN' AND orig_inv_no IN (SELECT inv_no FROM scope_invoices);   -- S4: credit notes follow their invoice

DROP TABLE IF EXISTS scope_payments;
CREATE TABLE scope_payments AS
SELECT p.pay_id
FROM stg_payments p, params x
WHERE (p.is_orphan = 0 AND p.inv_no IN (SELECT inv_no FROM scope_invoices))   -- S5: payments follow their invoice
   OR (p.is_orphan = 1 AND p.pay_date >= x.cutoff
       AND p.owner IN (SELECT cust_id FROM scope_customers));                  -- S5: unmatched cash inside the window

-- ---------------------------------------------------------------- customers

DROP TABLE IF EXISTS exp_customers;
CREATE TABLE exp_customers AS
SELECT c.cust_id                              AS legacy_customer_id,
       v.merged_legacy_ids,
       c.name,
       CASE WHEN c.email_ok = 1 THEN c.email_raw END AS email,     -- invalid addresses load blank (DEC-BPM-006)
       c.country,
       c.currency,
       c.created_date,
       sm.target_status                       AS status,
       sm.invoice_hold
FROM stg_customers c
JOIN stg_survivors v ON v.cust_id = c.cust_id
JOIN scope_customers sc ON sc.cust_id = c.cust_id
LEFT JOIN map_customer_status sm ON sm.legacy_status = v.group_status;   -- unmapped status shows as a difference (DQ-20)

-- ---------------------------------------------------------------- subscriptions

DROP TABLE IF EXISTS exp_subscriptions_all;
CREATE TABLE exp_subscriptions_all AS
SELECT s.sub_id                               AS legacy_subscription_id,
       s.owner                                AS customer,
       pm.target_plan_id                      AS plan_id,
       s.seats                                AS quantity,
       s.start_date,
       s.end_date,
       sm.target_status                       AS status,
       NULLIF(sm.cancel_reason, '')           AS cancel_reason
FROM stg_subscriptions s
JOIN scope_subscriptions USING (sub_id)
LEFT JOIN map_sub_status sm ON sm.legacy_status = s.status            -- unmapped status shows as a difference (DQ-20)
LEFT JOIN map_plan pm ON pm.legacy_plan_code = s.plan_code;

-- The platform rejects a subscription with no seats (DQ-13). Those are expected rejects, not loads.
DROP TABLE IF EXISTS exp_rejects;
CREATE TABLE exp_rejects AS
SELECT 'subscription' AS entity, legacy_subscription_id AS legacy_key, 'quantity must be at least 1' AS reason
FROM exp_subscriptions_all WHERE quantity < 1;

DROP TABLE IF EXISTS exp_subscriptions;
CREATE TABLE exp_subscriptions AS
SELECT * FROM exp_subscriptions_all WHERE quantity >= 1;

-- ---------------------------------------------------------------- invoices

DROP TABLE IF EXISTS exp_payments_applied;
CREATE TABLE exp_payments_applied AS
SELECT p.inv_no, SUM(p.amount_c) AS paid_c
FROM stg_payments p JOIN scope_payments USING (pay_id)
WHERE p.is_orphan = 0
GROUP BY p.inv_no;

DROP TABLE IF EXISTS exp_invoices;
CREATE TABLE exp_invoices AS
SELECT i.inv_no                               AS legacy_invoice_no,
       i.owner                                AS customer,
       i.sub_id                               AS subscription,
       i.inv_date                             AS invoice_date,
       i.due_date,
       i.currency,
       i.net_c                                AS subtotal_c,
       i.tax_c                                AS tax_c,         -- tax as billed, not recalculated (DEC-BPM-007)
       i.gross_c                              AS total_c,       -- total as billed, even where it is a cent off (DQ-08)
       COALESCE(a.paid_c, 0)                  AS amount_paid_c,
       CASE WHEN m.target_status IN ('open', 'uncollectible') THEN i.gross_c - COALESCE(a.paid_c, 0) ELSE 0 END
                                              AS amount_due_c,
       m.target_status                        AS status
FROM stg_invoices i
JOIN scope_invoices USING (inv_no)
LEFT JOIN map_inv_status m ON m.legacy_status = i.status            -- unmapped status shows as a difference (DQ-20)
LEFT JOIN exp_payments_applied a ON a.inv_no = i.inv_no;

DROP TABLE IF EXISTS exp_credit_notes;
CREATE TABLE exp_credit_notes AS
SELECT i.inv_no                               AS legacy_credit_note_no,
       i.orig_inv_no                          AS invoice,
       i.owner                                AS customer,
       i.inv_date                             AS credit_date,
       i.currency,
       -i.net_c                               AS subtotal_c,     -- legacy stores credits negative; platform positive
       -i.tax_c                               AS tax_c,
       -i.gross_c                             AS total_c
FROM stg_invoices i
JOIN scope_credit_notes USING (inv_no);

-- ---------------------------------------------------------------- payments

DROP TABLE IF EXISTS exp_payments;
CREATE TABLE exp_payments AS
SELECT p.pay_id                               AS legacy_payment_id,
       p.owner                                AS customer,
       CASE WHEN p.is_orphan = 0 THEN p.inv_no END AS invoice,
       p.pay_date                             AS paid_date,
       p.currency,
       p.amount_c,
       mm.target_method                       AS method,
       CASE WHEN p.is_orphan = 1 THEN 'true' ELSE 'false' END AS unapplied   -- unmatched cash loads as unapplied (DEC-BPM-008)
FROM stg_payments p
JOIN scope_payments USING (pay_id)
LEFT JOIN map_method mm ON mm.legacy_method = p.method;

CREATE INDEX ix_exp_inv   ON exp_invoices(legacy_invoice_no);
CREATE INDEX ix_exp_pay   ON exp_payments(legacy_payment_id);
CREATE INDEX ix_exp_sub   ON exp_subscriptions(legacy_subscription_id);
CREATE INDEX ix_exp_cus   ON exp_customers(legacy_customer_id);
CREATE INDEX ix_exp_crn   ON exp_credit_notes(legacy_credit_note_no);
