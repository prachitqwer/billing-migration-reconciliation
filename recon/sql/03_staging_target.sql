-- 03  Actual target: the platform's load files, put back onto legacy keys.
--
-- tgt_* are the files the loader produced, loaded as text. The platform's own
-- ids (cus_, sub_, in_, cn_, py_) are resolved to the legacy keys they carry so
-- that every comparison is legacy key against legacy key.

DROP TABLE IF EXISTS act_customers;
CREATE TABLE act_customers AS
SELECT legacy_customer_id,
       merged_legacy_ids,
       name,
       NULLIF(email, '')      AS email,
       country,
       currency,
       created_date,
       status,
       invoice_hold,
       customer_id
FROM tgt_customers;
CREATE INDEX ix_act_cus_id ON act_customers(customer_id);

DROP TABLE IF EXISTS act_subscriptions;
CREATE TABLE act_subscriptions AS
SELECT s.legacy_subscription_id,
       c.legacy_customer_id   AS customer,
       s.plan_id,
       CAST(s.quantity AS INTEGER) AS quantity,
       s.start_date,
       NULLIF(s.end_date, '') AS end_date,
       s.status,
       NULLIF(s.cancel_reason, '') AS cancel_reason,
       s.subscription_id,
       s.customer_id
FROM tgt_subscriptions s
LEFT JOIN act_customers c ON c.customer_id = s.customer_id;
CREATE INDEX ix_act_sub_id ON act_subscriptions(subscription_id);

DROP TABLE IF EXISTS act_invoices;
CREATE TABLE act_invoices AS
SELECT i.legacy_invoice_no,
       c.legacy_customer_id   AS customer,
       s.legacy_subscription_id AS subscription,
       i.invoice_date,
       NULLIF(i.due_date, '') AS due_date,
       i.currency,
       CAST(ROUND(CAST(i.subtotal    AS REAL) * 100) AS INTEGER) AS subtotal_c,
       CAST(ROUND(CAST(i.tax         AS REAL) * 100) AS INTEGER) AS tax_c,
       CAST(ROUND(CAST(i.total       AS REAL) * 100) AS INTEGER) AS total_c,
       CAST(ROUND(CAST(i.amount_paid AS REAL) * 100) AS INTEGER) AS amount_paid_c,
       CAST(ROUND(CAST(i.amount_due  AS REAL) * 100) AS INTEGER) AS amount_due_c,
       i.status,
       i.invoice_id,
       i.customer_id,
       NULLIF(i.subscription_id, '') AS subscription_id
FROM tgt_invoices i
LEFT JOIN act_customers c ON c.customer_id = i.customer_id
LEFT JOIN act_subscriptions s ON s.subscription_id = NULLIF(i.subscription_id, '');
CREATE INDEX ix_act_inv_id ON act_invoices(invoice_id);

DROP TABLE IF EXISTS act_credit_notes;
CREATE TABLE act_credit_notes AS
SELECT n.legacy_credit_note_no,
       i.legacy_invoice_no    AS invoice,
       c.legacy_customer_id   AS customer,
       n.credit_date,
       n.currency,
       CAST(ROUND(CAST(n.subtotal AS REAL) * 100) AS INTEGER) AS subtotal_c,
       CAST(ROUND(CAST(n.tax      AS REAL) * 100) AS INTEGER) AS tax_c,
       CAST(ROUND(CAST(n.total    AS REAL) * 100) AS INTEGER) AS total_c,
       n.credit_note_id,
       n.invoice_id,
       n.customer_id
FROM tgt_credit_notes n
LEFT JOIN act_invoices i ON i.invoice_id = n.invoice_id
LEFT JOIN act_customers c ON c.customer_id = n.customer_id;

DROP TABLE IF EXISTS act_payments;
CREATE TABLE act_payments AS
SELECT p.legacy_payment_id,
       c.legacy_customer_id   AS customer,
       i.legacy_invoice_no    AS invoice,
       p.paid_date,
       p.currency,
       CAST(ROUND(CAST(p.amount AS REAL) * 100) AS INTEGER) AS amount_c,
       p.method,
       p.unapplied,
       p.payment_id,
       p.customer_id,
       NULLIF(p.invoice_id, '') AS invoice_id
FROM tgt_payments p
LEFT JOIN act_customers c ON c.customer_id = p.customer_id
LEFT JOIN act_invoices i ON i.invoice_id = NULLIF(p.invoice_id, '');

CREATE INDEX ix_act_inv   ON act_invoices(legacy_invoice_no);
CREATE INDEX ix_act_pay   ON act_payments(legacy_payment_id);
CREATE INDEX ix_act_sub   ON act_subscriptions(legacy_subscription_id);
CREATE INDEX ix_act_cus   ON act_customers(legacy_customer_id);
CREATE INDEX ix_act_crn   ON act_credit_notes(legacy_credit_note_no);
