-- 40  Referential integrity and internal consistency inside the loaded target.
--     These look only at the target, so they don't depend on the expected target
--     being right: if the reconciliation and the loader misread a rule the same
--     way, a broken link or an invoice that doesn't add up still shows here.

DROP TABLE IF EXISTS ri_detail;
CREATE TABLE ri_detail (check_id TEXT, entity TEXT, target_key TEXT, legacy_key TEXT, issue TEXT);

INSERT INTO ri_detail
SELECT 'RC-RI-01', 'subscription', subscription_id, legacy_subscription_id, 'customer ' || customer_id || ' not found'
FROM act_subscriptions WHERE customer IS NULL;

INSERT INTO ri_detail
SELECT 'RC-RI-02', 'invoice', invoice_id, legacy_invoice_no, 'customer ' || customer_id || ' not found'
FROM act_invoices WHERE customer IS NULL;

INSERT INTO ri_detail
SELECT 'RC-RI-03', 'invoice', invoice_id, legacy_invoice_no, 'subscription ' || subscription_id || ' not found'
FROM act_invoices WHERE subscription_id IS NOT NULL AND subscription IS NULL;

INSERT INTO ri_detail
SELECT 'RC-RI-04', 'credit note', credit_note_id, legacy_credit_note_no, 'invoice ' || COALESCE(invoice_id, '(blank)') || ' not found'
FROM act_credit_notes WHERE invoice IS NULL;

INSERT INTO ri_detail
SELECT 'RC-RI-05', 'payment', payment_id, legacy_payment_id, 'customer ' || customer_id || ' not found'
FROM act_payments WHERE customer IS NULL;

INSERT INTO ri_detail
SELECT 'RC-RI-06', 'payment', payment_id, legacy_payment_id,
       CASE WHEN unapplied = 'false' AND invoice_id IS NULL THEN 'applied payment with no invoice'
            WHEN unapplied = 'false' AND invoice IS NULL    THEN 'invoice ' || invoice_id || ' not found'
            ELSE 'unapplied payment linked to an invoice' END
FROM act_payments
WHERE (unapplied = 'false' AND (invoice_id IS NULL OR invoice IS NULL))
   OR (unapplied = 'true' AND invoice_id IS NOT NULL);

INSERT INTO ri_detail
SELECT 'RC-RI-07', 'subscription', subscription_id, legacy_subscription_id, 'plan ' || COALESCE(plan_id, '(blank)') || ' is not a mapped platform plan'
FROM act_subscriptions WHERE plan_id IS NULL OR plan_id NOT IN (SELECT target_plan_id FROM map_plan);

INSERT INTO ri_detail
SELECT 'RC-RI-08', 'invoice', i.invoice_id, i.legacy_invoice_no, 'invoice in ' || i.currency || ', customer bills in ' || c.currency
FROM act_invoices i JOIN act_customers c ON c.customer_id = i.customer_id
WHERE i.currency <> c.currency;

INSERT INTO ri_detail
SELECT 'RC-RI-09', 'payment', p.payment_id, p.legacy_payment_id, 'payment in ' || p.currency || ', invoice in ' || i.currency
FROM act_payments p JOIN act_invoices i ON i.invoice_id = p.invoice_id
WHERE p.currency <> i.currency;

INSERT INTO ri_detail
SELECT 'RC-RI-10', 'invoice', invoice_id, legacy_invoice_no,
       CASE WHEN total_c < 0 THEN 'negative invoice total'
            WHEN amount_paid_c > total_c THEN 'paid more than the total'
            ELSE 'amount due does not equal total less paid' END
FROM act_invoices
WHERE total_c < 0
   OR amount_paid_c > total_c
   OR amount_due_c <> CASE WHEN status IN ('open', 'uncollectible') THEN total_c - amount_paid_c ELSE 0 END;

-- Added after mock 1: nothing in a month-end extract can be dated after the extract.
-- Eight invoices dated October in the September extract were the tell for DEF-BPM-001.
INSERT INTO ri_detail
SELECT 'RC-RI-11', 'invoice', invoice_id, legacy_invoice_no, 'dated ' || invoice_date || ', after the extract date'
FROM act_invoices, params WHERE invoice_date > as_of
UNION ALL
SELECT 'RC-RI-11', 'credit note', credit_note_id, legacy_credit_note_no, 'dated ' || credit_date || ', after the extract date'
FROM act_credit_notes, params WHERE credit_date > as_of
UNION ALL
SELECT 'RC-RI-11', 'payment', payment_id, legacy_payment_id, 'dated ' || paid_date || ', after the extract date'
FROM act_payments, params WHERE paid_date > as_of;

INSERT INTO checks (check_id, level, entity, title, compared, failures)
VALUES
 ('RC-RI-01', 'RI', 'subscriptions', 'Subscription points at a loaded customer',      (SELECT COUNT(*) FROM act_subscriptions), (SELECT COUNT(*) FROM ri_detail WHERE check_id = 'RC-RI-01')),
 ('RC-RI-02', 'RI', 'invoices',      'Invoice points at a loaded customer',           (SELECT COUNT(*) FROM act_invoices),      (SELECT COUNT(*) FROM ri_detail WHERE check_id = 'RC-RI-02')),
 ('RC-RI-03', 'RI', 'invoices',      'Invoice subscription link resolves',            (SELECT COUNT(*) FROM act_invoices WHERE subscription_id IS NOT NULL), (SELECT COUNT(*) FROM ri_detail WHERE check_id = 'RC-RI-03')),
 ('RC-RI-04', 'RI', 'credit notes',  'Credit note points at a loaded invoice',        (SELECT COUNT(*) FROM act_credit_notes),  (SELECT COUNT(*) FROM ri_detail WHERE check_id = 'RC-RI-04')),
 ('RC-RI-05', 'RI', 'payments',      'Payment points at a loaded customer',           (SELECT COUNT(*) FROM act_payments),      (SELECT COUNT(*) FROM ri_detail WHERE check_id = 'RC-RI-05')),
 ('RC-RI-06', 'RI', 'payments',      'Applied payments link to an invoice; unapplied do not', (SELECT COUNT(*) FROM act_payments), (SELECT COUNT(*) FROM ri_detail WHERE check_id = 'RC-RI-06')),
 ('RC-RI-07', 'RI', 'subscriptions', 'Plan is one of the mapped platform plans',      (SELECT COUNT(*) FROM act_subscriptions), (SELECT COUNT(*) FROM ri_detail WHERE check_id = 'RC-RI-07')),
 ('RC-RI-08', 'RI', 'invoices',      'Invoice currency matches the customer',         (SELECT COUNT(*) FROM act_invoices),      (SELECT COUNT(*) FROM ri_detail WHERE check_id = 'RC-RI-08')),
 ('RC-RI-09', 'RI', 'payments',      'Payment currency matches its invoice',          (SELECT COUNT(*) FROM act_payments WHERE invoice_id IS NOT NULL), (SELECT COUNT(*) FROM ri_detail WHERE check_id = 'RC-RI-09')),
 ('RC-RI-10', 'RI', 'invoices',      'Invoice amounts add up (total, paid, due)',     (SELECT COUNT(*) FROM act_invoices),      (SELECT COUNT(*) FROM ri_detail WHERE check_id = 'RC-RI-10')),
 ('RC-RI-11', 'RI', 'all',           'No invoice, credit note or payment dated after the extract date',
  (SELECT COUNT(*) FROM act_invoices) + (SELECT COUNT(*) FROM act_credit_notes) + (SELECT COUNT(*) FROM act_payments),
  (SELECT COUNT(*) FROM ri_detail WHERE check_id = 'RC-RI-11'));
