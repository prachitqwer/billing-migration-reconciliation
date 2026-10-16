-- 10  Level 1, completeness. Did every record that should arrive arrive, once,
--     and did nothing arrive that shouldn't?
--
-- Two views of the same question:
--   l1_bridge   counts from the legacy extract down to the target, per entity;
--               legacy rows must equal merged + out of scope + expected rejects + expected loads
--   l1_keys     the record-level differences: missing in target, in target but not
--               expected, or loaded more than once

DROP TABLE IF EXISTS l1_bridge;
CREATE TABLE l1_bridge (
    entity TEXT, source_rows INTEGER, merged INTEGER, out_of_scope INTEGER, expected_rejects INTEGER,
    expected_loads INTEGER, actual_loads INTEGER, actual_rejects INTEGER, missing_in_target INTEGER,
    not_expected INTEGER, loaded_twice INTEGER, bridge_balances INTEGER
);

DROP TABLE IF EXISTS l1_keys;
CREATE TABLE l1_keys (check_id TEXT, entity TEXT, legacy_key TEXT, issue TEXT);

-- customers
INSERT INTO l1_keys
SELECT 'RC-L1-01', 'customer', legacy_customer_id, 'missing in target'
FROM exp_customers WHERE legacy_customer_id NOT IN (SELECT legacy_customer_id FROM act_customers)
UNION ALL
SELECT 'RC-L1-01', 'customer', legacy_customer_id, 'in target, not expected'
FROM act_customers WHERE legacy_customer_id NOT IN (SELECT legacy_customer_id FROM exp_customers);

INSERT INTO l1_keys
SELECT 'RC-L1-01', 'customer', legacy_customer_id, 'loaded more than once'
FROM act_customers GROUP BY legacy_customer_id HAVING COUNT(*) > 1;

INSERT INTO l1_bridge
SELECT 'customers',
       (SELECT COUNT(*) FROM lb_customers),
       (SELECT COUNT(*) FROM stg_customer_groups WHERE cust_id <> survivor),
       (SELECT COUNT(*) FROM stg_survivors WHERE cust_id NOT IN (SELECT cust_id FROM scope_customers)),
       0,
       (SELECT COUNT(*) FROM exp_customers),
       (SELECT COUNT(*) FROM act_customers),
       0,
       (SELECT COUNT(*) FROM l1_keys WHERE check_id = 'RC-L1-01' AND issue = 'missing in target'),
       (SELECT COUNT(*) FROM l1_keys WHERE check_id = 'RC-L1-01' AND issue = 'in target, not expected'),
       (SELECT COUNT(*) FROM l1_keys WHERE check_id = 'RC-L1-01' AND issue = 'loaded more than once'),
       0;

-- subscriptions
INSERT INTO l1_keys
SELECT 'RC-L1-02', 'subscription', legacy_subscription_id, 'missing in target'
FROM exp_subscriptions WHERE legacy_subscription_id NOT IN (SELECT legacy_subscription_id FROM act_subscriptions)
UNION ALL
SELECT 'RC-L1-02', 'subscription', legacy_subscription_id, 'in target, not expected'
FROM act_subscriptions WHERE legacy_subscription_id NOT IN (SELECT legacy_subscription_id FROM exp_subscriptions);

-- load rejects: the platform should reject exactly the records we expect it to
INSERT INTO l1_keys
SELECT 'RC-L1-03', entity, legacy_key, 'expected reject, not rejected'
FROM exp_rejects WHERE entity || '|' || legacy_key NOT IN (SELECT entity || '|' || legacy_key FROM tgt_load_rejects)
UNION ALL
SELECT 'RC-L1-03', entity, legacy_key, 'rejected, not expected'
FROM tgt_load_rejects WHERE entity || '|' || legacy_key NOT IN (SELECT entity || '|' || legacy_key FROM exp_rejects);

INSERT INTO l1_keys
SELECT 'RC-L1-02', 'subscription', legacy_subscription_id, 'loaded more than once'
FROM act_subscriptions GROUP BY legacy_subscription_id HAVING COUNT(*) > 1;

INSERT INTO l1_bridge
SELECT 'subscriptions',
       (SELECT COUNT(*) FROM lb_subscriptions),
       0,
       (SELECT COUNT(*) FROM stg_subscriptions WHERE sub_id NOT IN (SELECT sub_id FROM scope_subscriptions)),
       (SELECT COUNT(*) FROM exp_rejects WHERE entity = 'subscription'),
       (SELECT COUNT(*) FROM exp_subscriptions),
       (SELECT COUNT(*) FROM act_subscriptions),
       (SELECT COUNT(*) FROM tgt_load_rejects WHERE entity = 'subscription'),
       (SELECT COUNT(*) FROM l1_keys WHERE check_id = 'RC-L1-02' AND issue = 'missing in target'),
       (SELECT COUNT(*) FROM l1_keys WHERE check_id = 'RC-L1-02' AND issue = 'in target, not expected'),
       (SELECT COUNT(*) FROM l1_keys WHERE check_id = 'RC-L1-02' AND issue = 'loaded more than once'),
       0;

-- invoices (legacy invoice rows of type INV)
INSERT INTO l1_keys
SELECT 'RC-L1-04', 'invoice', legacy_invoice_no, 'missing in target'
FROM exp_invoices WHERE legacy_invoice_no NOT IN (SELECT legacy_invoice_no FROM act_invoices)
UNION ALL
SELECT 'RC-L1-04', 'invoice', legacy_invoice_no, 'in target, not expected'
FROM act_invoices WHERE legacy_invoice_no NOT IN (SELECT legacy_invoice_no FROM exp_invoices);

INSERT INTO l1_keys
SELECT 'RC-L1-04', 'invoice', legacy_invoice_no, 'loaded more than once'
FROM act_invoices GROUP BY legacy_invoice_no HAVING COUNT(*) > 1;

INSERT INTO l1_bridge
SELECT 'invoices',
       (SELECT COUNT(*) FROM lb_invoices WHERE inv_type = 'INV'),
       0,
       (SELECT COUNT(*) FROM stg_invoices WHERE inv_type = 'INV' AND inv_no NOT IN (SELECT inv_no FROM scope_invoices)),
       0,
       (SELECT COUNT(*) FROM exp_invoices),
       (SELECT COUNT(*) FROM act_invoices),
       0,
       (SELECT COUNT(*) FROM l1_keys WHERE check_id = 'RC-L1-04' AND issue = 'missing in target'),
       (SELECT COUNT(*) FROM l1_keys WHERE check_id = 'RC-L1-04' AND issue = 'in target, not expected'),
       (SELECT COUNT(*) FROM l1_keys WHERE check_id = 'RC-L1-04' AND issue = 'loaded more than once'),
       0;

-- credit notes (legacy invoice rows of type CRN)
INSERT INTO l1_keys
SELECT 'RC-L1-05', 'credit note', legacy_credit_note_no, 'missing in target'
FROM exp_credit_notes WHERE legacy_credit_note_no NOT IN (SELECT legacy_credit_note_no FROM act_credit_notes)
UNION ALL
SELECT 'RC-L1-05', 'credit note', legacy_credit_note_no, 'in target, not expected'
FROM act_credit_notes WHERE legacy_credit_note_no NOT IN (SELECT legacy_credit_note_no FROM exp_credit_notes);

INSERT INTO l1_keys
SELECT 'RC-L1-05', 'credit note', legacy_credit_note_no, 'loaded more than once'
FROM act_credit_notes GROUP BY legacy_credit_note_no HAVING COUNT(*) > 1;

INSERT INTO l1_bridge
SELECT 'credit notes',
       (SELECT COUNT(*) FROM lb_invoices WHERE inv_type = 'CRN'),
       0,
       (SELECT COUNT(*) FROM stg_invoices WHERE inv_type = 'CRN' AND inv_no NOT IN (SELECT inv_no FROM scope_credit_notes)),
       0,
       (SELECT COUNT(*) FROM exp_credit_notes),
       (SELECT COUNT(*) FROM act_credit_notes),
       0,
       (SELECT COUNT(*) FROM l1_keys WHERE check_id = 'RC-L1-05' AND issue = 'missing in target'),
       (SELECT COUNT(*) FROM l1_keys WHERE check_id = 'RC-L1-05' AND issue = 'in target, not expected'),
       (SELECT COUNT(*) FROM l1_keys WHERE check_id = 'RC-L1-05' AND issue = 'loaded more than once'),
       0;

-- payments
INSERT INTO l1_keys
SELECT 'RC-L1-06', 'payment', legacy_payment_id, 'missing in target'
FROM exp_payments WHERE legacy_payment_id NOT IN (SELECT legacy_payment_id FROM act_payments)
UNION ALL
SELECT 'RC-L1-06', 'payment', legacy_payment_id, 'in target, not expected'
FROM act_payments WHERE legacy_payment_id NOT IN (SELECT legacy_payment_id FROM exp_payments);

INSERT INTO l1_keys
SELECT 'RC-L1-06', 'payment', legacy_payment_id, 'loaded more than once'
FROM act_payments GROUP BY legacy_payment_id HAVING COUNT(*) > 1;

INSERT INTO l1_bridge
SELECT 'payments',
       (SELECT COUNT(*) FROM lb_payments),
       0,
       (SELECT COUNT(*) FROM stg_payments WHERE pay_id NOT IN (SELECT pay_id FROM scope_payments)),
       0,
       (SELECT COUNT(*) FROM exp_payments),
       (SELECT COUNT(*) FROM act_payments),
       0,
       (SELECT COUNT(*) FROM l1_keys WHERE check_id = 'RC-L1-06' AND issue = 'missing in target'),
       (SELECT COUNT(*) FROM l1_keys WHERE check_id = 'RC-L1-06' AND issue = 'in target, not expected'),
       (SELECT COUNT(*) FROM l1_keys WHERE check_id = 'RC-L1-06' AND issue = 'loaded more than once'),
       0;

UPDATE l1_bridge SET bridge_balances =
    CASE WHEN source_rows = merged + out_of_scope + expected_rejects + expected_loads THEN 1 ELSE 0 END;

-- one result row per check: key-level differences, plus one failure if the bridge doesn't balance
INSERT INTO checks (check_id, level, entity, title, compared, failures)
VALUES
 ('RC-L1-01', 'L1', 'customers',     'Every in-scope customer loaded exactly once, nothing extra',
  (SELECT expected_loads FROM l1_bridge WHERE entity = 'customers'),
  (SELECT COUNT(*) FROM l1_keys WHERE check_id = 'RC-L1-01') + (SELECT 1 - bridge_balances FROM l1_bridge WHERE entity = 'customers')),
 ('RC-L1-02', 'L1', 'subscriptions', 'Every in-scope subscription loaded exactly once, nothing extra',
  (SELECT expected_loads FROM l1_bridge WHERE entity = 'subscriptions'),
  (SELECT COUNT(*) FROM l1_keys WHERE check_id = 'RC-L1-02') + (SELECT 1 - bridge_balances FROM l1_bridge WHERE entity = 'subscriptions')),
 ('RC-L1-03', 'L1', 'subscriptions', 'Platform rejected exactly the expected records',
  (SELECT expected_rejects FROM l1_bridge WHERE entity = 'subscriptions'),
  (SELECT COUNT(*) FROM l1_keys WHERE check_id = 'RC-L1-03')),
 ('RC-L1-04', 'L1', 'invoices',      'Every in-scope invoice loaded exactly once, nothing extra',
  (SELECT expected_loads FROM l1_bridge WHERE entity = 'invoices'),
  (SELECT COUNT(*) FROM l1_keys WHERE check_id = 'RC-L1-04') + (SELECT 1 - bridge_balances FROM l1_bridge WHERE entity = 'invoices')),
 ('RC-L1-05', 'L1', 'credit notes',  'Every in-scope credit note loaded exactly once, as a credit note',
  (SELECT expected_loads FROM l1_bridge WHERE entity = 'credit notes'),
  (SELECT COUNT(*) FROM l1_keys WHERE check_id = 'RC-L1-05') + (SELECT 1 - bridge_balances FROM l1_bridge WHERE entity = 'credit notes')),
 ('RC-L1-06', 'L1', 'payments',      'Every in-scope payment loaded exactly once, nothing extra',
  (SELECT expected_loads FROM l1_bridge WHERE entity = 'payments'),
  (SELECT COUNT(*) FROM l1_keys WHERE check_id = 'RC-L1-06') + (SELECT 1 - bridge_balances FROM l1_bridge WHERE entity = 'payments'));
