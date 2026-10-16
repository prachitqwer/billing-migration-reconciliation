-- 30  Level 3, field by field. For every record that is in both the expected and
--     the actual target, compare each mapped field. Only differences are stored.
--
-- All fields are compared here; the run config (config/mock*.json, l3_fields) decides
-- which fields count towards the result, so coverage can grow between mocks.
-- money() formats integer cents as 0.00 for the report.

DROP TABLE IF EXISTS l3_compared;
CREATE TABLE l3_compared (entity TEXT, rows_compared INTEGER);
DROP TABLE IF EXISTS l3_diffs;
CREATE TABLE l3_diffs (entity TEXT, legacy_key TEXT, field TEXT, expected TEXT, actual TEXT);

-- customers
INSERT INTO l3_compared SELECT 'customers', COUNT(*) FROM exp_customers e JOIN act_customers a USING (legacy_customer_id);
INSERT INTO l3_diffs
SELECT 'customers', e.legacy_customer_id, 'name', e.name, a.name FROM exp_customers e JOIN act_customers a USING (legacy_customer_id) WHERE e.name IS NOT a.name
UNION ALL
SELECT 'customers', e.legacy_customer_id, 'email', e.email, a.email FROM exp_customers e JOIN act_customers a USING (legacy_customer_id) WHERE e.email IS NOT a.email
UNION ALL
SELECT 'customers', e.legacy_customer_id, 'country', e.country, a.country FROM exp_customers e JOIN act_customers a USING (legacy_customer_id) WHERE e.country IS NOT a.country
UNION ALL
SELECT 'customers', e.legacy_customer_id, 'currency', e.currency, a.currency FROM exp_customers e JOIN act_customers a USING (legacy_customer_id) WHERE e.currency IS NOT a.currency
UNION ALL
SELECT 'customers', e.legacy_customer_id, 'status', e.status, a.status FROM exp_customers e JOIN act_customers a USING (legacy_customer_id) WHERE e.status IS NOT a.status
UNION ALL
SELECT 'customers', e.legacy_customer_id, 'invoice_hold', e.invoice_hold, a.invoice_hold FROM exp_customers e JOIN act_customers a USING (legacy_customer_id) WHERE e.invoice_hold IS NOT a.invoice_hold
UNION ALL
SELECT 'customers', e.legacy_customer_id, 'merged_legacy_ids', e.merged_legacy_ids, a.merged_legacy_ids FROM exp_customers e JOIN act_customers a USING (legacy_customer_id) WHERE e.merged_legacy_ids IS NOT a.merged_legacy_ids
UNION ALL
SELECT 'customers', e.legacy_customer_id, 'created_date', e.created_date, a.created_date FROM exp_customers e JOIN act_customers a USING (legacy_customer_id) WHERE e.created_date IS NOT a.created_date;

-- subscriptions
INSERT INTO l3_compared SELECT 'subscriptions', COUNT(*) FROM exp_subscriptions e JOIN act_subscriptions a USING (legacy_subscription_id);
INSERT INTO l3_diffs
SELECT 'subscriptions', e.legacy_subscription_id, 'customer', e.customer, a.customer FROM exp_subscriptions e JOIN act_subscriptions a USING (legacy_subscription_id) WHERE e.customer IS NOT a.customer
UNION ALL
SELECT 'subscriptions', e.legacy_subscription_id, 'plan_id', e.plan_id, a.plan_id FROM exp_subscriptions e JOIN act_subscriptions a USING (legacy_subscription_id) WHERE e.plan_id IS NOT a.plan_id
UNION ALL
SELECT 'subscriptions', e.legacy_subscription_id, 'quantity', e.quantity, a.quantity FROM exp_subscriptions e JOIN act_subscriptions a USING (legacy_subscription_id) WHERE e.quantity IS NOT a.quantity
UNION ALL
SELECT 'subscriptions', e.legacy_subscription_id, 'start_date', e.start_date, a.start_date FROM exp_subscriptions e JOIN act_subscriptions a USING (legacy_subscription_id) WHERE e.start_date IS NOT a.start_date
UNION ALL
SELECT 'subscriptions', e.legacy_subscription_id, 'end_date', e.end_date, a.end_date FROM exp_subscriptions e JOIN act_subscriptions a USING (legacy_subscription_id) WHERE e.end_date IS NOT a.end_date
UNION ALL
SELECT 'subscriptions', e.legacy_subscription_id, 'status', e.status, a.status FROM exp_subscriptions e JOIN act_subscriptions a USING (legacy_subscription_id) WHERE e.status IS NOT a.status
UNION ALL
SELECT 'subscriptions', e.legacy_subscription_id, 'cancel_reason', e.cancel_reason, a.cancel_reason FROM exp_subscriptions e JOIN act_subscriptions a USING (legacy_subscription_id) WHERE e.cancel_reason IS NOT a.cancel_reason;

-- invoices
INSERT INTO l3_compared SELECT 'invoices', COUNT(*) FROM exp_invoices e JOIN act_invoices a USING (legacy_invoice_no);
INSERT INTO l3_diffs
SELECT 'invoices', e.legacy_invoice_no, 'customer', e.customer, a.customer FROM exp_invoices e JOIN act_invoices a USING (legacy_invoice_no) WHERE e.customer IS NOT a.customer
UNION ALL
SELECT 'invoices', e.legacy_invoice_no, 'subscription', e.subscription, a.subscription FROM exp_invoices e JOIN act_invoices a USING (legacy_invoice_no) WHERE e.subscription IS NOT a.subscription
UNION ALL
SELECT 'invoices', e.legacy_invoice_no, 'invoice_date', e.invoice_date, a.invoice_date FROM exp_invoices e JOIN act_invoices a USING (legacy_invoice_no) WHERE e.invoice_date IS NOT a.invoice_date
UNION ALL
SELECT 'invoices', e.legacy_invoice_no, 'due_date', e.due_date, a.due_date FROM exp_invoices e JOIN act_invoices a USING (legacy_invoice_no) WHERE e.due_date IS NOT a.due_date
UNION ALL
SELECT 'invoices', e.legacy_invoice_no, 'currency', e.currency, a.currency FROM exp_invoices e JOIN act_invoices a USING (legacy_invoice_no) WHERE e.currency IS NOT a.currency
UNION ALL
SELECT 'invoices', e.legacy_invoice_no, 'subtotal', money(e.subtotal_c), money(a.subtotal_c) FROM exp_invoices e JOIN act_invoices a USING (legacy_invoice_no) WHERE e.subtotal_c IS NOT a.subtotal_c
UNION ALL
SELECT 'invoices', e.legacy_invoice_no, 'tax', money(e.tax_c), money(a.tax_c) FROM exp_invoices e JOIN act_invoices a USING (legacy_invoice_no) WHERE e.tax_c IS NOT a.tax_c
UNION ALL
SELECT 'invoices', e.legacy_invoice_no, 'total', money(e.total_c), money(a.total_c) FROM exp_invoices e JOIN act_invoices a USING (legacy_invoice_no) WHERE e.total_c IS NOT a.total_c
UNION ALL
SELECT 'invoices', e.legacy_invoice_no, 'amount_paid', money(e.amount_paid_c), money(a.amount_paid_c) FROM exp_invoices e JOIN act_invoices a USING (legacy_invoice_no) WHERE e.amount_paid_c IS NOT a.amount_paid_c
UNION ALL
SELECT 'invoices', e.legacy_invoice_no, 'amount_due', money(e.amount_due_c), money(a.amount_due_c) FROM exp_invoices e JOIN act_invoices a USING (legacy_invoice_no) WHERE e.amount_due_c IS NOT a.amount_due_c
UNION ALL
SELECT 'invoices', e.legacy_invoice_no, 'status', e.status, a.status FROM exp_invoices e JOIN act_invoices a USING (legacy_invoice_no) WHERE e.status IS NOT a.status;

-- credit_notes
INSERT INTO l3_compared SELECT 'credit_notes', COUNT(*) FROM exp_credit_notes e JOIN act_credit_notes a USING (legacy_credit_note_no);
INSERT INTO l3_diffs
SELECT 'credit_notes', e.legacy_credit_note_no, 'customer', e.customer, a.customer FROM exp_credit_notes e JOIN act_credit_notes a USING (legacy_credit_note_no) WHERE e.customer IS NOT a.customer
UNION ALL
SELECT 'credit_notes', e.legacy_credit_note_no, 'invoice', e.invoice, a.invoice FROM exp_credit_notes e JOIN act_credit_notes a USING (legacy_credit_note_no) WHERE e.invoice IS NOT a.invoice
UNION ALL
SELECT 'credit_notes', e.legacy_credit_note_no, 'credit_date', e.credit_date, a.credit_date FROM exp_credit_notes e JOIN act_credit_notes a USING (legacy_credit_note_no) WHERE e.credit_date IS NOT a.credit_date
UNION ALL
SELECT 'credit_notes', e.legacy_credit_note_no, 'currency', e.currency, a.currency FROM exp_credit_notes e JOIN act_credit_notes a USING (legacy_credit_note_no) WHERE e.currency IS NOT a.currency
UNION ALL
SELECT 'credit_notes', e.legacy_credit_note_no, 'subtotal', money(e.subtotal_c), money(a.subtotal_c) FROM exp_credit_notes e JOIN act_credit_notes a USING (legacy_credit_note_no) WHERE e.subtotal_c IS NOT a.subtotal_c
UNION ALL
SELECT 'credit_notes', e.legacy_credit_note_no, 'tax', money(e.tax_c), money(a.tax_c) FROM exp_credit_notes e JOIN act_credit_notes a USING (legacy_credit_note_no) WHERE e.tax_c IS NOT a.tax_c
UNION ALL
SELECT 'credit_notes', e.legacy_credit_note_no, 'total', money(e.total_c), money(a.total_c) FROM exp_credit_notes e JOIN act_credit_notes a USING (legacy_credit_note_no) WHERE e.total_c IS NOT a.total_c;

-- payments
INSERT INTO l3_compared SELECT 'payments', COUNT(*) FROM exp_payments e JOIN act_payments a USING (legacy_payment_id);
INSERT INTO l3_diffs
SELECT 'payments', e.legacy_payment_id, 'customer', e.customer, a.customer FROM exp_payments e JOIN act_payments a USING (legacy_payment_id) WHERE e.customer IS NOT a.customer
UNION ALL
SELECT 'payments', e.legacy_payment_id, 'invoice', e.invoice, a.invoice FROM exp_payments e JOIN act_payments a USING (legacy_payment_id) WHERE e.invoice IS NOT a.invoice
UNION ALL
SELECT 'payments', e.legacy_payment_id, 'currency', e.currency, a.currency FROM exp_payments e JOIN act_payments a USING (legacy_payment_id) WHERE e.currency IS NOT a.currency
UNION ALL
SELECT 'payments', e.legacy_payment_id, 'amount', money(e.amount_c), money(a.amount_c) FROM exp_payments e JOIN act_payments a USING (legacy_payment_id) WHERE e.amount_c IS NOT a.amount_c
UNION ALL
SELECT 'payments', e.legacy_payment_id, 'unapplied', e.unapplied, a.unapplied FROM exp_payments e JOIN act_payments a USING (legacy_payment_id) WHERE e.unapplied IS NOT a.unapplied
UNION ALL
SELECT 'payments', e.legacy_payment_id, 'paid_date', e.paid_date, a.paid_date FROM exp_payments e JOIN act_payments a USING (legacy_payment_id) WHERE e.paid_date IS NOT a.paid_date
UNION ALL
SELECT 'payments', e.legacy_payment_id, 'method', e.method, a.method FROM exp_payments e JOIN act_payments a USING (legacy_payment_id) WHERE e.method IS NOT a.method;
