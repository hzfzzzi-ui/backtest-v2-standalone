-- Apply DDL for CSI1000 PIT refresh sidecar.
-- Scope: refresh-level snapshot evidence for 000852.SH PIT imports.

CREATE TABLE IF NOT EXISTS public.pit_index_constituent_refresh_membership (
    index_code VARCHAR NOT NULL,
    refresh_date DATE NOT NULL,
    symbol VARCHAR NOT NULL,
    constituent_start_date DATE NOT NULL,
    source TEXT,
    event_type TEXT,
    snapshot_trade_date DATE,
    rebalance_calendar_version TEXT,
    rebalance_calendar_source TEXT,
    rebalance_calendar_generated_at TEXT,
    source_url TEXT,
    source_note TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (index_code, refresh_date, symbol)
);

CREATE INDEX IF NOT EXISTS idx_pit_index_constituent_refresh_membership_mapping
ON public.pit_index_constituent_refresh_membership (index_code, symbol, constituent_start_date);

ANALYZE public.pit_index_constituent_refresh_membership;
