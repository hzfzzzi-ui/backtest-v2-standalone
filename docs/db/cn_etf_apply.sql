CREATE TABLE IF NOT EXISTS public.pit_cn_etf_master (
    ts_code VARCHAR(16) PRIMARY KEY,
    symbol VARCHAR(16) NOT NULL UNIQUE,
    name TEXT NOT NULL,
    exchange VARCHAR(8) NOT NULL,
    batch_id TEXT NOT NULL,
    exposure_bucket TEXT NOT NULL,
    list_date DATE,
    delist_date DATE,
    source TEXT NOT NULL,
    latest_refresh_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.pams_cn_etf_daily (
    trade_date DATE NOT NULL,
    symbol VARCHAR(16) NOT NULL,
    ts_code VARCHAR(16) NOT NULL,
    open DOUBLE PRECISION,
    high DOUBLE PRECISION,
    low DOUBLE PRECISION,
    close DOUBLE PRECISION,
    volume DOUBLE PRECISION,
    turnover DOUBLE PRECISION,
    amount DOUBLE PRECISION,
    price_adjust_mode TEXT NOT NULL DEFAULT 'none',
    price_series_semantics TEXT NOT NULL DEFAULT 'executable_price_only_not_total_return',
    source TEXT NOT NULL,
    build_run_id TEXT NOT NULL,
    latest_refresh_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (trade_date, symbol)
);

CREATE INDEX IF NOT EXISTS idx_pams_cn_etf_daily_symbol_date
ON public.pams_cn_etf_daily (symbol, trade_date);

CREATE TABLE IF NOT EXISTS public.cn_etf_data_coverage_daily (
    ts_code VARCHAR(16) PRIMARY KEY,
    symbol VARCHAR(16) NOT NULL UNIQUE,
    batch_id TEXT NOT NULL,
    exposure_bucket TEXT NOT NULL,
    coverage_start DATE,
    coverage_end DATE,
    row_count BIGINT NOT NULL DEFAULT 0,
    latest_refresh_at TIMESTAMPTZ,
    daily_table TEXT NOT NULL DEFAULT 'pams_cn_etf_daily',
    price_series_semantics TEXT NOT NULL DEFAULT 'executable_price_only_not_total_return',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
