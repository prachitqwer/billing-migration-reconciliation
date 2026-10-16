-- 01  Staging: the legacy extract, cleaned to the rules in the mapping spec (docs/03).
--
-- Raw tables lb_* are loaded as text exactly as delivered. Nothing here changes
-- the meaning of a value; it only trims, parses and standardises so that the
-- expected-target build (02) can apply the business rules.
--
-- Functions registered by recon/engine.py:
--   nfold(text)     casefold, drop '.' and ',', collapse spaces   (DQ-05 matching)
--   email_ok(text)  1 if the address has a mailbox, a domain and a TLD

DROP TABLE IF EXISTS stg_customers;
CREATE TABLE stg_customers AS
SELECT TRIM(c.cust_id)                                   AS cust_id,
       c.company_name                                    AS name,
       TRIM(c.contact_email)                             AS email_raw,
       email_ok(TRIM(c.contact_email))                   AS email_ok,
       c.country                                         AS country_raw,
       m.iso2                                            AS country,
       c.currency,
       c.tax_region,
       CASE WHEN c.created_on LIKE '__/__/____'
            THEN substr(c.created_on, 7, 4) || '-' || substr(c.created_on, 1, 2) || '-' || substr(c.created_on, 4, 2)
            ELSE c.created_on END                        AS created_date,
       c.status,
       CASE WHEN email_ok(TRIM(c.contact_email)) = 1
            THEN nfold(c.company_name) || '|' || lower(TRIM(c.contact_email))
            ELSE '__' || TRIM(c.cust_id) END             AS dup_key
FROM lb_customers c
LEFT JOIN map_country m ON m.legacy_value = c.country;

-- Survivorship (DEC-BPM-003): earliest created customer wins, then lowest id.
DROP TABLE IF EXISTS stg_customer_groups;
CREATE TABLE stg_customer_groups AS
SELECT cust_id,
       dup_key,
       FIRST_VALUE(cust_id) OVER (PARTITION BY dup_key ORDER BY created_date, cust_id) AS survivor
FROM stg_customers;

-- Status of a merged customer: on hold beats active beats inactive.
DROP TABLE IF EXISTS stg_survivors;
CREATE TABLE stg_survivors AS
SELECT g.survivor                                                        AS cust_id,
       CASE WHEN SUM(c.status = 'H') > 0 THEN 'H'
            WHEN SUM(c.status = 'A') > 0 THEN 'A'
            ELSE 'I' END                                                 AS group_status,
       COALESCE(group_concat(CASE WHEN c.cust_id <> g.survivor THEN c.cust_id END, ';' ORDER BY c.cust_id), '')
                                                                         AS merged_legacy_ids,
       COUNT(*) - 1                                                      AS merged_count
FROM stg_customer_groups g
JOIN stg_customers c ON c.cust_id = g.cust_id
GROUP BY g.survivor;

DROP TABLE IF EXISTS stg_subscriptions;
CREATE TABLE stg_subscriptions AS
SELECT s.sub_id,
       TRIM(s.cust_id)                 AS cust_id,
       g.survivor                      AS owner,
       s.plan_code,
       CAST(s.seats AS INTEGER)        AS seats,
       s.start_date,
       NULLIF(s.end_date, '')          AS end_date,
       s.status
FROM lb_subscriptions s
JOIN stg_customer_groups g ON g.cust_id = TRIM(s.cust_id);

DROP TABLE IF EXISTS stg_invoices;
CREATE TABLE stg_invoices AS
SELECT i.inv_no,
       i.inv_type,
       NULLIF(i.orig_inv_no, '')                                               AS orig_inv_no,
       TRIM(i.cust_id)                                                         AS cust_id,
       g.survivor                                                              AS owner,
       NULLIF(i.sub_id, '')                                                    AS sub_id,
       i.inv_ts,
       substr(i.inv_ts, 1, 10)                                                 AS inv_date,   -- business date in New York
       NULLIF(i.due_date, '')                                                  AS due_date,
       i.currency,
       CAST(ROUND(CAST(REPLACE(i.net_amount,   ',', '') AS REAL) * 100) AS INTEGER) AS net_c,
       CAST(ROUND(CAST(REPLACE(i.tax_amount,   ',', '') AS REAL) * 100) AS INTEGER) AS tax_c,
       CAST(ROUND(CAST(REPLACE(i.gross_amount, ',', '') AS REAL) * 100) AS INTEGER) AS gross_c,
       i.status
FROM lb_invoices i
JOIN stg_customer_groups g ON g.cust_id = TRIM(i.cust_id);

DROP TABLE IF EXISTS stg_payments;
CREATE TABLE stg_payments AS
SELECT p.pay_id,
       TRIM(p.cust_id)                                                         AS cust_id,
       g.survivor                                                              AS owner,
       NULLIF(p.inv_no, '')                                                    AS inv_no,
       p.pay_ts,
       substr(p.pay_ts, 1, 10)                                                 AS pay_date,
       CAST(ROUND(CAST(REPLACE(p.amount, ',', '') AS REAL) * 100) AS INTEGER) AS amount_c,
       p.currency,
       p.method,
       CASE WHEN NULLIF(p.inv_no, '') IS NULL
              OR p.inv_no NOT IN (SELECT inv_no FROM lb_invoices) THEN 1 ELSE 0 END AS is_orphan
FROM lb_payments p
JOIN stg_customer_groups g ON g.cust_id = TRIM(p.cust_id);

CREATE INDEX ix_stg_inv_no   ON stg_invoices(inv_no);
CREATE INDEX ix_stg_inv_own  ON stg_invoices(owner);
CREATE INDEX ix_stg_pay_inv  ON stg_payments(inv_no);
