-- L2 rollback DDL for optimize-core-db-structure
-- Run outside an explicit transaction block.

DROP INDEX CONCURRENTLY IF EXISTS public.idx_pit_index_constituents_lookup;
DROP INDEX CONCURRENTLY IF EXISTS public.idx_pit_industry_history_l1_lookup;
