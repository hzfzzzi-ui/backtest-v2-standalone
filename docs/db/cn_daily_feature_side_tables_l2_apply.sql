-- L2 apply DDL for add-cn-daily-basic-and-moneyflow-side-tables
-- Scope: add two CN_A daily side tables without changing pams_ohlcv_daily semantics.

CREATE TABLE IF NOT EXISTS public.pit_stock_daily_basic (
    symbol TEXT NOT NULL,
    trade_date DATE NOT NULL,
    turnover_rate DOUBLE PRECISION NULL,
    turnover_rate_f DOUBLE PRECISION NULL,
    source TEXT NOT NULL DEFAULT 'tushare_daily_basic',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (symbol, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_pit_stock_daily_basic_trade_date
ON public.pit_stock_daily_basic (trade_date DESC);

CREATE TABLE IF NOT EXISTS public.pit_stock_moneyflow (
    symbol TEXT NOT NULL,
    trade_date DATE NOT NULL,
    buy_sm_vol BIGINT NULL,
    sell_sm_vol BIGINT NULL,
    buy_md_vol BIGINT NULL,
    sell_md_vol BIGINT NULL,
    buy_lg_vol BIGINT NULL,
    sell_lg_vol BIGINT NULL,
    buy_elg_vol BIGINT NULL,
    sell_elg_vol BIGINT NULL,
    net_mf_vol BIGINT NULL,
    buy_sm_amount DOUBLE PRECISION NULL,
    sell_sm_amount DOUBLE PRECISION NULL,
    buy_md_amount DOUBLE PRECISION NULL,
    sell_md_amount DOUBLE PRECISION NULL,
    buy_lg_amount DOUBLE PRECISION NULL,
    sell_lg_amount DOUBLE PRECISION NULL,
    buy_elg_amount DOUBLE PRECISION NULL,
    sell_elg_amount DOUBLE PRECISION NULL,
    net_mf_amount DOUBLE PRECISION NULL,
    source TEXT NOT NULL DEFAULT 'tushare_moneyflow',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (symbol, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_pit_stock_moneyflow_trade_date
ON public.pit_stock_moneyflow (trade_date DESC);
