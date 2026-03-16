-- L2 apply DDL for optimize-core-db-structure
-- Scope: add only non-semantic indexes for PIT lookup hot paths.
-- Safety:
-- 1. Use CONCURRENTLY to avoid blocking writes for long periods.
-- 2. Run outside an explicit transaction block.
-- 3. Verify with EXPLAIN before and after execution.

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pit_index_constituents_lookup
ON public.pit_index_constituents (index_code, start_date, end_date, symbol);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pit_industry_history_l1_lookup
ON public.pit_industry_history (industry_l1, start_date, end_date, ts_code);

ANALYZE public.pit_index_constituents;
ANALYZE public.pit_industry_history;
