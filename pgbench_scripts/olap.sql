-- OLAP benchmark script for pgbench (scale=50 → ~5 M rows in pgbench_accounts)
-- Each client runs this script in a loop; one iteration = one "transaction".
-- Queries are chosen to stress work_mem (sort/hash), parallel seq scan,
-- and the query planner (effective_cache_size, random_page_cost).

-- Q1: full-table aggregation — parallel seq scan + hash aggregate
SELECT bid,
       COUNT(*)                       AS accounts,
       SUM(abalance)                  AS total_balance,
       AVG(abalance)                  AS avg_balance,
       MAX(abalance) - MIN(abalance)  AS balance_range
FROM pgbench_accounts
GROUP BY bid
ORDER BY total_balance DESC;

-- Q2: join + aggregation — hash join, work_mem sensitive
SELECT a.bid,
       t.tid,
       COUNT(a.aid)    AS accounts,
       SUM(a.abalance) AS balance_sum
FROM pgbench_accounts a
JOIN pgbench_tellers t ON a.bid = t.bid
GROUP BY a.bid, t.tid
ORDER BY a.bid, t.tid;

-- Q3: ordered-set aggregation — large sort, tests work_mem / temp files
SELECT bid,
       PERCENTILE_CONT(0.5)  WITHIN GROUP (ORDER BY abalance) AS median_balance,
       PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY abalance) AS p95_balance
FROM pgbench_accounts
GROUP BY bid
ORDER BY bid;
