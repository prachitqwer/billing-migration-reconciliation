-- 05  Data quality rules on the legacy extract (catalog: docs/04_data_quality_rules.md).
--
-- Run during profiling and again at the start of every mock, so a fresh extract
-- that brings new problems shows up before anything is loaded. A failing rule is
-- not automatically a blocker: most have a handling rule in the mapping spec.

DROP TABLE IF EXISTS dq_detail;
CREATE TABLE dq_detail (rule_id TEXT, source_table TEXT, record_key TEXT, value TEXT);

DROP TABLE IF EXISTS dq_results;
CREATE TABLE dq_results (rule_id TEXT, title TEXT, source_table TEXT, severity TEXT, rows_checked INTEGER, rows_failing INTEGER);

-- DQ-01 customer id padded with spaces (breaks joins)
INSERT INTO dq_detail
SELECT 'DQ-01', 'lb_invoices', inv_no, '"' || cust_id || '"' FROM lb_invoices WHERE cust_id <> TRIM(cust_id)
UNION ALL SELECT 'DQ-01', 'lb_payments', pay_id, '"' || cust_id || '"' FROM lb_payments WHERE cust_id <> TRIM(cust_id)
UNION ALL SELECT 'DQ-01', 'lb_subscriptions', sub_id, '"' || cust_id || '"' FROM lb_subscriptions WHERE cust_id <> TRIM(cust_id)
UNION ALL SELECT 'DQ-01', 'lb_customers', cust_id, '"' || cust_id || '"' FROM lb_customers WHERE cust_id <> TRIM(cust_id);
INSERT INTO dq_results VALUES ('DQ-01', 'Customer id padded with spaces', 'all', 'High',
  (SELECT COUNT(*) FROM lb_invoices) + (SELECT COUNT(*) FROM lb_payments) + (SELECT COUNT(*) FROM lb_subscriptions) + (SELECT COUNT(*) FROM lb_customers),
  (SELECT COUNT(*) FROM dq_detail WHERE rule_id = 'DQ-01'));

-- DQ-02 country not an ISO 3166 alpha-2 code
INSERT INTO dq_detail
SELECT 'DQ-02', 'lb_customers', cust_id, country FROM lb_customers
WHERE country NOT IN (SELECT DISTINCT iso2 FROM map_country WHERE legacy_value = iso2);
INSERT INTO dq_results VALUES ('DQ-02', 'Country not an ISO 3166 alpha-2 code', 'lb_customers', 'Medium',
  (SELECT COUNT(*) FROM lb_customers), (SELECT COUNT(*) FROM dq_detail WHERE rule_id = 'DQ-02'));

-- DQ-03 country value with no entry in the country map (would load blank)
INSERT INTO dq_detail
SELECT 'DQ-03', 'lb_customers', cust_id, country FROM lb_customers WHERE country NOT IN (SELECT legacy_value FROM map_country);
INSERT INTO dq_results VALUES ('DQ-03', 'Country value missing from the country map', 'lb_customers', 'Blocker',
  (SELECT COUNT(*) FROM lb_customers), (SELECT COUNT(*) FROM dq_detail WHERE rule_id = 'DQ-03'));

-- DQ-04 created_on not in ISO format
INSERT INTO dq_detail
SELECT 'DQ-04', 'lb_customers', cust_id, created_on FROM lb_customers WHERE created_on NOT LIKE '____-__-__';
INSERT INTO dq_results VALUES ('DQ-04', 'Customer created date not in YYYY-MM-DD', 'lb_customers', 'Low',
  (SELECT COUNT(*) FROM lb_customers), (SELECT COUNT(*) FROM dq_detail WHERE rule_id = 'DQ-04'));

-- DQ-05 same company and email under two customer ids
INSERT INTO dq_detail
SELECT 'DQ-05', 'lb_customers', g.cust_id, 'duplicate of ' || g.survivor FROM stg_customer_groups g WHERE g.cust_id <> g.survivor;
INSERT INTO dq_results VALUES ('DQ-05', 'Duplicate customer (same company and email)', 'lb_customers', 'High',
  (SELECT COUNT(*) FROM lb_customers), (SELECT COUNT(*) FROM dq_detail WHERE rule_id = 'DQ-05'));

-- DQ-06 contact email missing or not a valid address
INSERT INTO dq_detail
SELECT 'DQ-06', 'lb_customers', cust_id, CASE WHEN contact_email = '' THEN '(blank)' ELSE contact_email END
FROM lb_customers WHERE email_ok(TRIM(contact_email)) = 0;
INSERT INTO dq_results VALUES ('DQ-06', 'Contact email missing or invalid', 'lb_customers', 'Medium',
  (SELECT COUNT(*) FROM lb_customers), (SELECT COUNT(*) FROM dq_detail WHERE rule_id = 'DQ-06'));

-- DQ-07 amount exported with a thousands separator
INSERT INTO dq_detail
SELECT 'DQ-07', 'lb_invoices', inv_no, net_amount || ' / ' || tax_amount || ' / ' || gross_amount FROM lb_invoices
WHERE net_amount LIKE '%,%' OR tax_amount LIKE '%,%' OR gross_amount LIKE '%,%'
UNION ALL SELECT 'DQ-07', 'lb_payments', pay_id, amount FROM lb_payments WHERE amount LIKE '%,%';
INSERT INTO dq_results VALUES ('DQ-07', 'Amount exported with a thousands separator', 'lb_invoices, lb_payments', 'Low',
  (SELECT COUNT(*) FROM lb_invoices) + (SELECT COUNT(*) FROM lb_payments), (SELECT COUNT(*) FROM dq_detail WHERE rule_id = 'DQ-07'));

-- DQ-08 gross does not equal net plus tax
INSERT INTO dq_detail
SELECT 'DQ-08', 'lb_invoices', inv_no, printf('net %s + tax %s, gross %s', money(net_c), money(tax_c), money(gross_c))
FROM stg_invoices WHERE gross_c <> net_c + tax_c;
INSERT INTO dq_results VALUES ('DQ-08', 'Gross does not equal net plus tax', 'lb_invoices', 'Medium',
  (SELECT COUNT(*) FROM lb_invoices), (SELECT COUNT(*) FROM dq_detail WHERE rule_id = 'DQ-08'));

-- DQ-09 subscription on a plan code that is not in the plan table
INSERT INTO dq_detail
SELECT 'DQ-09', 'lb_subscriptions', sub_id, plan_code FROM lb_subscriptions WHERE plan_code NOT IN (SELECT plan_code FROM lb_plans);
INSERT INTO dq_results VALUES ('DQ-09', 'Plan code not in the plan table', 'lb_subscriptions', 'High',
  (SELECT COUNT(*) FROM lb_subscriptions), (SELECT COUNT(*) FROM dq_detail WHERE rule_id = 'DQ-09'));

-- DQ-10 plan code with no entry in the plan map (would load with no plan)
INSERT INTO dq_detail
SELECT 'DQ-10', 'lb_subscriptions', sub_id, plan_code FROM lb_subscriptions WHERE plan_code NOT IN (SELECT legacy_plan_code FROM map_plan);
INSERT INTO dq_results VALUES ('DQ-10', 'Plan code missing from the plan map', 'lb_subscriptions', 'Blocker',
  (SELECT COUNT(*) FROM lb_subscriptions), (SELECT COUNT(*) FROM dq_detail WHERE rule_id = 'DQ-10'));

-- DQ-11 payment with no matching invoice
INSERT INTO dq_detail
SELECT 'DQ-11', 'lb_payments', pay_id, CASE WHEN inv_no IS NULL THEN '(no invoice number)' ELSE inv_no || ' not found' END
FROM stg_payments WHERE is_orphan = 1;
INSERT INTO dq_results VALUES ('DQ-11', 'Payment with no matching invoice', 'lb_payments', 'High',
  (SELECT COUNT(*) FROM lb_payments), (SELECT COUNT(*) FROM dq_detail WHERE rule_id = 'DQ-11'));

-- DQ-12 credit notes held in the invoice table as negative invoices
INSERT INTO dq_detail
SELECT 'DQ-12', 'lb_invoices', inv_no, 'credit for ' || orig_inv_no FROM lb_invoices WHERE inv_type = 'CRN';
INSERT INTO dq_results VALUES ('DQ-12', 'Credit note stored as a negative invoice', 'lb_invoices', 'Info',
  (SELECT COUNT(*) FROM lb_invoices), (SELECT COUNT(*) FROM dq_detail WHERE rule_id = 'DQ-12'));

-- DQ-13 subscription with zero seats
INSERT INTO dq_detail
SELECT 'DQ-13', 'lb_subscriptions', sub_id, status || ', ' || start_date || ' to ' || end_date FROM lb_subscriptions WHERE CAST(seats AS INTEGER) < 1;
INSERT INTO dq_results VALUES ('DQ-13', 'Subscription with zero seats', 'lb_subscriptions', 'Medium',
  (SELECT COUNT(*) FROM lb_subscriptions), (SELECT COUNT(*) FROM dq_detail WHERE rule_id = 'DQ-13'));

-- DQ-14 payment currency differs from its invoice
INSERT INTO dq_detail
SELECT 'DQ-14', 'lb_payments', p.pay_id, p.currency || ' vs ' || i.currency
FROM stg_payments p JOIN stg_invoices i ON i.inv_no = p.inv_no WHERE p.currency <> i.currency;
INSERT INTO dq_results VALUES ('DQ-14', 'Payment currency differs from the invoice', 'lb_payments', 'High',
  (SELECT COUNT(*) FROM stg_payments WHERE is_orphan = 0), (SELECT COUNT(*) FROM dq_detail WHERE rule_id = 'DQ-14'));

-- DQ-15 invoice currency differs from the customer
INSERT INTO dq_detail
SELECT 'DQ-15', 'lb_invoices', i.inv_no, i.currency || ' vs ' || c.currency
FROM stg_invoices i JOIN stg_customers c ON c.cust_id = i.cust_id WHERE i.currency <> c.currency;
INSERT INTO dq_results VALUES ('DQ-15', 'Invoice currency differs from the customer', 'lb_invoices', 'High',
  (SELECT COUNT(*) FROM lb_invoices), (SELECT COUNT(*) FROM dq_detail WHERE rule_id = 'DQ-15'));

-- DQ-16 payments applied to an invoice add up to more than its gross
INSERT INTO dq_detail
SELECT 'DQ-16', 'lb_invoices', i.inv_no, printf('paid %s of %s', money(SUM(p.amount_c)), money(i.gross_c))
FROM stg_invoices i JOIN stg_payments p ON p.inv_no = i.inv_no
GROUP BY i.inv_no HAVING SUM(p.amount_c) > i.gross_c;
INSERT INTO dq_results VALUES ('DQ-16', 'Payments exceed the invoice gross', 'lb_invoices', 'High',
  (SELECT COUNT(*) FROM lb_invoices WHERE inv_type = 'INV'), (SELECT COUNT(*) FROM dq_detail WHERE rule_id = 'DQ-16'));

-- DQ-17 subscription ends before it starts
INSERT INTO dq_detail
SELECT 'DQ-17', 'lb_subscriptions', sub_id, start_date || ' to ' || end_date FROM lb_subscriptions WHERE end_date <> '' AND end_date < start_date;
INSERT INTO dq_results VALUES ('DQ-17', 'Subscription ends before it starts', 'lb_subscriptions', 'Medium',
  (SELECT COUNT(*) FROM lb_subscriptions), (SELECT COUNT(*) FROM dq_detail WHERE rule_id = 'DQ-17'));

-- DQ-18 child record whose customer id is not in the customer table
INSERT INTO dq_detail
SELECT 'DQ-18', 'lb_invoices', inv_no, cust_id FROM lb_invoices WHERE TRIM(cust_id) NOT IN (SELECT TRIM(cust_id) FROM lb_customers)
UNION ALL SELECT 'DQ-18', 'lb_payments', pay_id, cust_id FROM lb_payments WHERE TRIM(cust_id) NOT IN (SELECT TRIM(cust_id) FROM lb_customers)
UNION ALL SELECT 'DQ-18', 'lb_subscriptions', sub_id, cust_id FROM lb_subscriptions WHERE TRIM(cust_id) NOT IN (SELECT TRIM(cust_id) FROM lb_customers);
INSERT INTO dq_results VALUES ('DQ-18', 'Customer id not in the customer table', 'all', 'Blocker',
  (SELECT COUNT(*) FROM lb_invoices) + (SELECT COUNT(*) FROM lb_payments) + (SELECT COUNT(*) FROM lb_subscriptions),
  (SELECT COUNT(*) FROM dq_detail WHERE rule_id = 'DQ-18'));

-- DQ-19 open invoices older than the history window (they still migrate; Finance wanted the count)
INSERT INTO dq_detail
SELECT 'DQ-19', 'lb_invoices', i.inv_no, i.inv_date || ' ' || i.status FROM stg_invoices i, params p
WHERE i.inv_type = 'INV' AND i.inv_date < p.cutoff AND i.status IN ('OPEN', 'PART');
INSERT INTO dq_results VALUES ('DQ-19', 'Open invoice older than the 24-month window', 'lb_invoices', 'Info',
  (SELECT COUNT(*) FROM lb_invoices WHERE inv_type = 'INV'), (SELECT COUNT(*) FROM dq_detail WHERE rule_id = 'DQ-19'));

-- DQ-20 status or payment method with no entry in its value map (would load blank or default)
INSERT INTO dq_detail
SELECT 'DQ-20', 'lb_customers', cust_id, 'status ' || status FROM lb_customers WHERE status NOT IN (SELECT legacy_status FROM map_customer_status)
UNION ALL SELECT 'DQ-20', 'lb_subscriptions', sub_id, 'status ' || status FROM lb_subscriptions WHERE status NOT IN (SELECT legacy_status FROM map_sub_status)
UNION ALL SELECT 'DQ-20', 'lb_invoices', inv_no, 'status ' || status FROM lb_invoices WHERE inv_type = 'INV' AND status NOT IN (SELECT legacy_status FROM map_inv_status)
UNION ALL SELECT 'DQ-20', 'lb_payments', pay_id, 'method ' || method FROM lb_payments WHERE method NOT IN (SELECT legacy_method FROM map_method);
INSERT INTO dq_results VALUES ('DQ-20', 'Status or payment method missing from its value map', 'all', 'Blocker',
  (SELECT COUNT(*) FROM lb_customers) + (SELECT COUNT(*) FROM lb_subscriptions) + (SELECT COUNT(*) FROM lb_invoices WHERE inv_type = 'INV') + (SELECT COUNT(*) FROM lb_payments),
  (SELECT COUNT(*) FROM dq_detail WHERE rule_id = 'DQ-20'));
