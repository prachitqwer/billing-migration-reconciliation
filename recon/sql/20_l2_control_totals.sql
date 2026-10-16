-- 20  Level 2, control totals. Counts and money by the cuts Finance and Billing
--     Ops use, expected against actual. Tolerance is zero: one cent fails.
--
-- l2_detail holds one row per cut and measure; unit is 'count' or 'cents'.

DROP TABLE IF EXISTS l2_detail;
CREATE TABLE l2_detail (check_id TEXT, dimension TEXT, measure TEXT, unit TEXT, expected INTEGER, actual INTEGER, diff INTEGER);

-- RC-L2-01 customers by status and billing hold
WITH e AS (SELECT status || ' / hold=' || invoice_hold AS dim, COUNT(*) AS n FROM exp_customers GROUP BY 1),
     a AS (SELECT status || ' / hold=' || invoice_hold AS dim, COUNT(*) AS n FROM act_customers GROUP BY 1),
     j AS (SELECT COALESCE(e.dim, a.dim) AS dim, COALESCE(e.n, 0) AS en, COALESCE(a.n, 0) AS an
           FROM e FULL OUTER JOIN a ON a.dim = e.dim)
INSERT INTO l2_detail SELECT 'RC-L2-01', dim, 'customers', 'count', en, an, an - en FROM j;

-- RC-L2-02 customers by country and currency
WITH e AS (SELECT COALESCE(country, '(blank)') || ' / ' || currency AS dim, COUNT(*) AS n FROM exp_customers GROUP BY 1),
     a AS (SELECT COALESCE(country, '(blank)') || ' / ' || currency AS dim, COUNT(*) AS n FROM act_customers GROUP BY 1),
     j AS (SELECT COALESCE(e.dim, a.dim) AS dim, COALESCE(e.n, 0) AS en, COALESCE(a.n, 0) AS an
           FROM e FULL OUTER JOIN a ON a.dim = e.dim)
INSERT INTO l2_detail SELECT 'RC-L2-02', dim, 'customers', 'count', en, an, an - en FROM j;

-- RC-L2-03 subscriptions by status: count and seats
WITH e AS (SELECT status AS dim, COUNT(*) AS n, SUM(quantity) AS v FROM exp_subscriptions GROUP BY 1),
     a AS (SELECT status AS dim, COUNT(*) AS n, SUM(quantity) AS v FROM act_subscriptions GROUP BY 1),
     j AS (SELECT COALESCE(e.dim, a.dim) AS dim, COALESCE(e.n, 0) AS en, COALESCE(a.n, 0) AS an,
                  COALESCE(e.v, 0) AS ev, COALESCE(a.v, 0) AS av
           FROM e FULL OUTER JOIN a ON a.dim = e.dim)
INSERT INTO l2_detail
SELECT 'RC-L2-03', dim, 'subscriptions', 'count', en, an, an - en FROM j
UNION ALL SELECT 'RC-L2-03', dim, 'seats', 'count', ev, av, av - ev FROM j;

-- RC-L2-04 subscriptions by plan: count and seats
WITH e AS (SELECT COALESCE(plan_id, '(unmapped)') AS dim, COUNT(*) AS n, SUM(quantity) AS v FROM exp_subscriptions GROUP BY 1),
     a AS (SELECT COALESCE(plan_id, '(unmapped)') AS dim, COUNT(*) AS n, SUM(quantity) AS v FROM act_subscriptions GROUP BY 1),
     j AS (SELECT COALESCE(e.dim, a.dim) AS dim, COALESCE(e.n, 0) AS en, COALESCE(a.n, 0) AS an,
                  COALESCE(e.v, 0) AS ev, COALESCE(a.v, 0) AS av
           FROM e FULL OUTER JOIN a ON a.dim = e.dim)
INSERT INTO l2_detail
SELECT 'RC-L2-04', dim, 'subscriptions', 'count', en, an, an - en FROM j
UNION ALL SELECT 'RC-L2-04', dim, 'seats', 'count', ev, av, av - ev FROM j;

-- RC-L2-05 invoices by currency and invoice month: count and total
WITH e AS (SELECT currency || ' ' || substr(invoice_date, 1, 7) AS dim, COUNT(*) AS n, SUM(total_c) AS v FROM exp_invoices GROUP BY 1),
     a AS (SELECT currency || ' ' || substr(invoice_date, 1, 7) AS dim, COUNT(*) AS n, SUM(total_c) AS v FROM act_invoices GROUP BY 1),
     j AS (SELECT COALESCE(e.dim, a.dim) AS dim, COALESCE(e.n, 0) AS en, COALESCE(a.n, 0) AS an,
                  COALESCE(e.v, 0) AS ev, COALESCE(a.v, 0) AS av
           FROM e FULL OUTER JOIN a ON a.dim = e.dim)
INSERT INTO l2_detail
SELECT 'RC-L2-05', dim, 'invoices', 'count', en, an, an - en FROM j
UNION ALL SELECT 'RC-L2-05', dim, 'invoice total', 'cents', ev, av, av - ev FROM j;

-- RC-L2-06 invoices by status: count, total and amount still due
WITH e AS (SELECT status AS dim, COUNT(*) AS n, SUM(total_c) AS v, SUM(amount_due_c) AS d FROM exp_invoices GROUP BY 1),
     a AS (SELECT COALESCE(status, '(blank)') AS dim, COUNT(*) AS n, SUM(total_c) AS v, SUM(amount_due_c) AS d FROM act_invoices GROUP BY 1),
     j AS (SELECT COALESCE(e.dim, a.dim) AS dim, COALESCE(e.n, 0) AS en, COALESCE(a.n, 0) AS an,
                  COALESCE(e.v, 0) AS ev, COALESCE(a.v, 0) AS av, COALESCE(e.d, 0) AS ed, COALESCE(a.d, 0) AS ad
           FROM e FULL OUTER JOIN a ON a.dim = e.dim)
INSERT INTO l2_detail
SELECT 'RC-L2-06', dim, 'invoices', 'count', en, an, an - en FROM j
UNION ALL SELECT 'RC-L2-06', dim, 'invoice total', 'cents', ev, av, av - ev FROM j
UNION ALL SELECT 'RC-L2-06', dim, 'amount due', 'cents', ed, ad, ad - ed FROM j;

-- RC-L2-07 invoice tax by currency
WITH e AS (SELECT currency AS dim, SUM(tax_c) AS v FROM exp_invoices GROUP BY 1),
     a AS (SELECT currency AS dim, SUM(tax_c) AS v FROM act_invoices GROUP BY 1),
     j AS (SELECT COALESCE(e.dim, a.dim) AS dim, COALESCE(e.v, 0) AS ev, COALESCE(a.v, 0) AS av
           FROM e FULL OUTER JOIN a ON a.dim = e.dim)
INSERT INTO l2_detail SELECT 'RC-L2-07', dim, 'tax', 'cents', ev, av, av - ev FROM j;

-- RC-L2-08 credit notes by currency: count and total
WITH e AS (SELECT currency AS dim, COUNT(*) AS n, SUM(total_c) AS v FROM exp_credit_notes GROUP BY 1),
     a AS (SELECT currency AS dim, COUNT(*) AS n, SUM(total_c) AS v FROM act_credit_notes GROUP BY 1),
     j AS (SELECT COALESCE(e.dim, a.dim) AS dim, COALESCE(e.n, 0) AS en, COALESCE(a.n, 0) AS an,
                  COALESCE(e.v, 0) AS ev, COALESCE(a.v, 0) AS av
           FROM e FULL OUTER JOIN a ON a.dim = e.dim)
INSERT INTO l2_detail
SELECT 'RC-L2-08', dim, 'credit notes', 'count', en, an, an - en FROM j
UNION ALL SELECT 'RC-L2-08', dim, 'credit note total', 'cents', ev, av, av - ev FROM j;

-- RC-L2-09 payments by currency and payment month: count and amount
WITH e AS (SELECT currency || ' ' || substr(paid_date, 1, 7) AS dim, COUNT(*) AS n, SUM(amount_c) AS v FROM exp_payments GROUP BY 1),
     a AS (SELECT currency || ' ' || substr(paid_date, 1, 7) AS dim, COUNT(*) AS n, SUM(amount_c) AS v FROM act_payments GROUP BY 1),
     j AS (SELECT COALESCE(e.dim, a.dim) AS dim, COALESCE(e.n, 0) AS en, COALESCE(a.n, 0) AS an,
                  COALESCE(e.v, 0) AS ev, COALESCE(a.v, 0) AS av
           FROM e FULL OUTER JOIN a ON a.dim = e.dim)
INSERT INTO l2_detail
SELECT 'RC-L2-09', dim, 'payments', 'count', en, an, an - en FROM j
UNION ALL SELECT 'RC-L2-09', dim, 'payment amount', 'cents', ev, av, av - ev FROM j;

-- RC-L2-10 unapplied payments by currency
WITH e AS (SELECT currency AS dim, COUNT(*) AS n, SUM(amount_c) AS v FROM exp_payments WHERE unapplied = 'true' GROUP BY 1),
     a AS (SELECT currency AS dim, COUNT(*) AS n, SUM(amount_c) AS v FROM act_payments WHERE unapplied = 'true' GROUP BY 1),
     j AS (SELECT COALESCE(e.dim, a.dim) AS dim, COALESCE(e.n, 0) AS en, COALESCE(a.n, 0) AS an,
                  COALESCE(e.v, 0) AS ev, COALESCE(a.v, 0) AS av
           FROM e FULL OUTER JOIN a ON a.dim = e.dim)
INSERT INTO l2_detail
SELECT 'RC-L2-10', dim, 'unapplied payments', 'count', en, an, an - en FROM j
UNION ALL SELECT 'RC-L2-10', dim, 'unapplied amount', 'cents', ev, av, av - ev FROM j;

INSERT INTO checks (check_id, level, entity, title, compared, failures)
SELECT d.check_id, 'L2', t.entity, t.title, COUNT(*), SUM(d.diff <> 0)
FROM l2_detail d
JOIN (SELECT 'RC-L2-01' AS id, 'customers' AS entity, 'Customers by status and billing hold' AS title
      UNION ALL SELECT 'RC-L2-02', 'customers', 'Customers by country and currency'
      UNION ALL SELECT 'RC-L2-03', 'subscriptions', 'Subscriptions and seats by status'
      UNION ALL SELECT 'RC-L2-04', 'subscriptions', 'Subscriptions and seats by plan'
      UNION ALL SELECT 'RC-L2-05', 'invoices', 'Invoice count and total by currency and month'
      UNION ALL SELECT 'RC-L2-06', 'invoices', 'Invoice count, total and amount due by status'
      UNION ALL SELECT 'RC-L2-07', 'invoices', 'Invoice tax by currency'
      UNION ALL SELECT 'RC-L2-08', 'credit notes', 'Credit note count and total by currency'
      UNION ALL SELECT 'RC-L2-09', 'payments', 'Payment count and amount by currency and month'
      UNION ALL SELECT 'RC-L2-10', 'payments', 'Unapplied payments by currency') t ON t.id = d.check_id
GROUP BY d.check_id
ORDER BY d.check_id;
