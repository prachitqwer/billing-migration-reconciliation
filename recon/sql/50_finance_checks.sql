-- 50  Level 4, the numbers Finance signs off on. Same comparison as level 2,
--     but cut the way the Controller reads them: receivables, aging, customer
--     balances, and billing and cash for the extract month (params.close_month),
--     which Finance closes from legacy.
--
-- Open AR = amount due on open invoices less unapplied cash, per currency.
-- Credit notes carry no balance: legacy refunded every one through AP when it
-- was issued (DEC-BPM-012), so they are not in the balance views.
-- Aging buckets are days past due at params.as_of.

DROP TABLE IF EXISTS l4_detail;
CREATE TABLE l4_detail (check_id TEXT, dimension TEXT, measure TEXT, unit TEXT, expected INTEGER, actual INTEGER, diff INTEGER);

DROP VIEW IF EXISTS v_exp_balance;
CREATE VIEW v_exp_balance AS
SELECT customer, currency, SUM(v) AS balance_c FROM (
    SELECT customer, currency, amount_due_c AS v FROM exp_invoices WHERE status = 'open'
    UNION ALL
    SELECT customer, currency, -amount_c FROM exp_payments WHERE unapplied = 'true')
GROUP BY customer, currency;

DROP VIEW IF EXISTS v_act_balance;
CREATE VIEW v_act_balance AS
SELECT customer, currency, SUM(v) AS balance_c FROM (
    SELECT COALESCE(customer, '(unresolved)') AS customer, currency, amount_due_c AS v FROM act_invoices WHERE status = 'open'
    UNION ALL
    SELECT COALESCE(customer, '(unresolved)'), currency, -amount_c FROM act_payments WHERE unapplied = 'true')
GROUP BY customer, currency;

-- RC-L4-01 open receivables by currency
WITH e AS (SELECT currency AS dim, SUM(balance_c) AS v FROM v_exp_balance GROUP BY 1),
     a AS (SELECT currency AS dim, SUM(balance_c) AS v FROM v_act_balance GROUP BY 1),
     j AS (SELECT COALESCE(e.dim, a.dim) AS dim, COALESCE(e.v, 0) AS ev, COALESCE(a.v, 0) AS av
           FROM e FULL OUTER JOIN a ON a.dim = e.dim)
INSERT INTO l4_detail SELECT 'RC-L4-01', dim, 'open AR', 'cents', ev, av, av - ev FROM j;

-- RC-L4-02 aging by currency and bucket
WITH b AS (SELECT CASE WHEN julianday(p.as_of) - julianday(due_date) <= 0  THEN '0 current'
                       WHEN julianday(p.as_of) - julianday(due_date) <= 30 THEN '1 1-30'
                       WHEN julianday(p.as_of) - julianday(due_date) <= 60 THEN '2 31-60'
                       WHEN julianday(p.as_of) - julianday(due_date) <= 90 THEN '3 61-90'
                       ELSE '4 90+' END AS bucket, x.*
           FROM params p, (SELECT 'e' AS side, currency, due_date, amount_due_c FROM exp_invoices WHERE status = 'open'
                           UNION ALL
                           SELECT 'a', currency, due_date, amount_due_c FROM act_invoices WHERE status = 'open') x),
     e AS (SELECT currency || ' ' || bucket AS dim, SUM(amount_due_c) AS v FROM b WHERE side = 'e' GROUP BY 1),
     a AS (SELECT currency || ' ' || bucket AS dim, SUM(amount_due_c) AS v FROM b WHERE side = 'a' GROUP BY 1),
     j AS (SELECT COALESCE(e.dim, a.dim) AS dim, COALESCE(e.v, 0) AS ev, COALESCE(a.v, 0) AS av
           FROM e FULL OUTER JOIN a ON a.dim = e.dim)
INSERT INTO l4_detail SELECT 'RC-L4-02', dim, 'amount due', 'cents', ev, av, av - ev FROM j;

-- RC-L4-03 every customer's balance
WITH j AS (SELECT COALESCE(e.customer, a.customer) AS customer, COALESCE(e.currency, a.currency) AS currency,
                  COALESCE(e.balance_c, 0) AS ev, COALESCE(a.balance_c, 0) AS av
           FROM v_exp_balance e FULL OUTER JOIN v_act_balance a ON a.customer = e.customer AND a.currency = e.currency)
INSERT INTO l4_detail SELECT 'RC-L4-03', customer || ' ' || currency, 'balance', 'cents', ev, av, av - ev FROM j;

-- RC-L4-04 net billing for the extract month: invoices (not void) less credit notes dated in it
WITH e AS (SELECT currency AS dim, SUM(v) AS v FROM (
               SELECT currency, total_c AS v FROM exp_invoices, params WHERE substr(invoice_date, 1, 7) = close_month AND COALESCE(status, '') <> 'void'
               UNION ALL
               SELECT currency, -total_c FROM exp_credit_notes, params WHERE substr(credit_date, 1, 7) = close_month) GROUP BY 1),
     a AS (SELECT currency AS dim, SUM(v) AS v FROM (
               SELECT currency, total_c AS v FROM act_invoices, params WHERE substr(invoice_date, 1, 7) = close_month AND COALESCE(status, '') <> 'void'
               UNION ALL
               SELECT currency, -total_c FROM act_credit_notes, params WHERE substr(credit_date, 1, 7) = close_month) GROUP BY 1),
     j AS (SELECT COALESCE(e.dim, a.dim) AS dim, COALESCE(e.v, 0) AS ev, COALESCE(a.v, 0) AS av
           FROM e FULL OUTER JOIN a ON a.dim = e.dim)
INSERT INTO l4_detail SELECT 'RC-L4-04', dim, 'net billing', 'cents', ev, av, av - ev FROM j;

-- RC-L4-05 cash received in the extract month
WITH e AS (SELECT currency AS dim, SUM(amount_c) AS v FROM exp_payments, params WHERE substr(paid_date, 1, 7) = close_month GROUP BY 1),
     a AS (SELECT currency AS dim, SUM(amount_c) AS v FROM act_payments, params WHERE substr(paid_date, 1, 7) = close_month GROUP BY 1),
     j AS (SELECT COALESCE(e.dim, a.dim) AS dim, COALESCE(e.v, 0) AS ev, COALESCE(a.v, 0) AS av
           FROM e FULL OUTER JOIN a ON a.dim = e.dim)
INSERT INTO l4_detail SELECT 'RC-L4-05', dim, 'cash received', 'cents', ev, av, av - ev FROM j;

INSERT INTO checks (check_id, level, entity, title, compared, failures)
SELECT d.check_id, 'L4', t.entity, t.title, COUNT(*), SUM(d.diff <> 0)
FROM l4_detail d
JOIN (SELECT 'RC-L4-01' AS id, 'receivables' AS entity, 'Open receivables by currency' AS title
      UNION ALL SELECT 'RC-L4-02', 'receivables', 'Receivables aging by currency and bucket'
      UNION ALL SELECT 'RC-L4-03', 'receivables', 'Balance of every customer with money owed or cash on account'
      UNION ALL SELECT 'RC-L4-04', 'billing', 'Net billing for ' || (SELECT close_month FROM params) || ' by currency'
      UNION ALL SELECT 'RC-L4-05', 'cash', 'Cash received in ' || (SELECT close_month FROM params) || ' by currency') t ON t.id = d.check_id
GROUP BY d.check_id
ORDER BY d.check_id;
