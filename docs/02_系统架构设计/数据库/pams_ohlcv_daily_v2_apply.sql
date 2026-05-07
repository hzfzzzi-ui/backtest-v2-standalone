BEGIN;

CREATE TABLE IF NOT EXISTS public.raw_tushare_stock_basic (
    ts_code VARCHAR(12) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    name VARCHAR(100),
    exchange VARCHAR(10),
    market VARCHAR(20),
    list_status VARCHAR(1) NOT NULL,
    list_date DATE,
    delist_date DATE,
    industry VARCHAR(100),
    source_run_id TEXT NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (ts_code)
);

CREATE TABLE IF NOT EXISTS public.raw_tushare_trade_cal (
    exchange VARCHAR(10) NOT NULL,
    cal_date DATE NOT NULL,
    is_open BOOLEAN NOT NULL,
    pretrade_date DATE,
    source_run_id TEXT NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (exchange, cal_date)
);

CREATE TABLE IF NOT EXISTS public.raw_tushare_daily (
    ts_code VARCHAR(12) NOT NULL,
    trade_date DATE NOT NULL,
    open NUMERIC(12,4),
    high NUMERIC(12,4),
    low NUMERIC(12,4),
    close NUMERIC(12,4),
    pre_close NUMERIC(12,4),
    change NUMERIC(12,4),
    pct_chg DOUBLE PRECISION,
    vol DOUBLE PRECISION,
    amount DOUBLE PRECISION,
    source_run_id TEXT NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (ts_code, trade_date)
);

CREATE TABLE IF NOT EXISTS public.raw_tushare_adj_factor (
    ts_code VARCHAR(12) NOT NULL,
    trade_date DATE NOT NULL,
    adj_factor NUMERIC(14,6),
    source_run_id TEXT NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (ts_code, trade_date)
);

CREATE TABLE IF NOT EXISTS public.raw_tushare_daily_basic (
    ts_code VARCHAR(12) NOT NULL,
    trade_date DATE NOT NULL,
    close NUMERIC(12,4),
    turnover_rate DOUBLE PRECISION,
    turnover_rate_f DOUBLE PRECISION,
    volume_ratio DOUBLE PRECISION,
    float_share DOUBLE PRECISION,
    free_share DOUBLE PRECISION,
    circ_mv DOUBLE PRECISION,
    source_run_id TEXT NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (ts_code, trade_date)
);

CREATE TABLE IF NOT EXISTS public.raw_tushare_suspend_d (
    ts_code VARCHAR(12) NOT NULL,
    trade_date DATE NOT NULL,
    suspend_timing TEXT,
    suspend_type TEXT,
    source_run_id TEXT NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (ts_code, trade_date)
);

CREATE TABLE IF NOT EXISTS public.raw_tushare_stk_limit (
    ts_code VARCHAR(12) NOT NULL,
    trade_date DATE NOT NULL,
    up_limit NUMERIC(12,4),
    down_limit NUMERIC(12,4),
    source_run_id TEXT NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (ts_code, trade_date)
);

CREATE TABLE IF NOT EXISTS public.raw_tushare_moneyflow (
    ts_code VARCHAR(12) NOT NULL,
    trade_date DATE NOT NULL,
    buy_sm_vol BIGINT,
    sell_sm_vol BIGINT,
    buy_md_vol BIGINT,
    sell_md_vol BIGINT,
    buy_lg_vol BIGINT,
    sell_lg_vol BIGINT,
    buy_elg_vol BIGINT,
    sell_elg_vol BIGINT,
    net_mf_vol BIGINT,
    buy_sm_amount DOUBLE PRECISION,
    sell_sm_amount DOUBLE PRECISION,
    buy_md_amount DOUBLE PRECISION,
    sell_md_amount DOUBLE PRECISION,
    buy_lg_amount DOUBLE PRECISION,
    sell_lg_amount DOUBLE PRECISION,
    buy_elg_amount DOUBLE PRECISION,
    sell_elg_amount DOUBLE PRECISION,
    net_mf_amount DOUBLE PRECISION,
    source_run_id TEXT NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (ts_code, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_raw_tushare_trade_cal_cal_date
    ON public.raw_tushare_trade_cal (cal_date);
CREATE INDEX IF NOT EXISTS idx_raw_tushare_daily_trade_date
    ON public.raw_tushare_daily (trade_date);
CREATE INDEX IF NOT EXISTS idx_raw_tushare_adj_factor_trade_date
    ON public.raw_tushare_adj_factor (trade_date);
CREATE INDEX IF NOT EXISTS idx_raw_tushare_daily_basic_trade_date
    ON public.raw_tushare_daily_basic (trade_date);
CREATE INDEX IF NOT EXISTS idx_raw_tushare_suspend_d_trade_date
    ON public.raw_tushare_suspend_d (trade_date);
CREATE INDEX IF NOT EXISTS idx_raw_tushare_stk_limit_trade_date
    ON public.raw_tushare_stk_limit (trade_date);
CREATE INDEX IF NOT EXISTS idx_raw_tushare_moneyflow_trade_date
    ON public.raw_tushare_moneyflow (trade_date);

CREATE TABLE IF NOT EXISTS public.pit_security_symbol_lineage (
    current_symbol VARCHAR(20) NOT NULL,
    current_ts_code VARCHAR(12) NOT NULL,
    historical_symbol VARCHAR(20) NOT NULL,
    historical_ts_code VARCHAR(12) NOT NULL,
    phase_start DATE,
    phase_end DATE,
    phase_type VARCHAR(32) NOT NULL,
    mapping_source TEXT NOT NULL,
    mapping_confidence SMALLINT NOT NULL DEFAULT 1,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (current_symbol, historical_symbol, phase_type)
);

CREATE INDEX IF NOT EXISTS idx_pit_security_symbol_lineage_current_symbol
    ON public.pit_security_symbol_lineage (current_symbol, phase_type);
CREATE INDEX IF NOT EXISTS idx_pit_security_symbol_lineage_historical_symbol
    ON public.pit_security_symbol_lineage (historical_symbol);

INSERT INTO public.pit_security_symbol_lineage (
    current_symbol, current_ts_code, historical_symbol, historical_ts_code,
    phase_start, phase_end, phase_type, mapping_source, mapping_confidence, is_active, notes
) VALUES
    ('bj920047', '920047.BJ', 'bj430047', '430047.BJ', NULL, DATE '2021-11-14', 'bj_pre_20211115', 'official_bse_code_mapping_seed', 3, TRUE, 'Official BSE new-old code mapping seed'),
    ('bj920090', '920090.BJ', 'bj430090', '430090.BJ', NULL, DATE '2021-11-14', 'bj_pre_20211115', 'official_bse_code_mapping_seed', 3, TRUE, 'Official BSE new-old code mapping seed'),
    ('bj920139', '920139.BJ', 'bj430139', '430139.BJ', NULL, DATE '2021-11-14', 'bj_pre_20211115', 'official_bse_code_mapping_seed', 3, TRUE, 'Official BSE new-old code mapping seed'),
    ('bj920017', '920017.BJ', 'bj430017', '430017.BJ', NULL, DATE '2021-11-14', 'bj_pre_20211115', 'official_bse_code_mapping_seed', 3, TRUE, 'Official BSE new-old code mapping seed'),
    ('bj920198', '920198.BJ', 'bj430198', '430198.BJ', NULL, DATE '2021-11-14', 'bj_pre_20211115', 'official_bse_code_mapping_seed', 3, TRUE, 'Official BSE new-old code mapping seed'),
    ('bj920564', '920564.BJ', 'bj430564', '430564.BJ', NULL, DATE '2021-11-14', 'bj_pre_20211115', 'official_bse_code_mapping_seed', 3, TRUE, 'Official BSE new-old code mapping seed'),
    ('bj920425', '920425.BJ', 'bj430425', '430425.BJ', NULL, DATE '2021-11-14', 'bj_pre_20211115', 'official_bse_code_mapping_seed', 3, TRUE, 'Official BSE new-old code mapping seed'),
    ('bj920556', '920556.BJ', 'bj430556', '430556.BJ', NULL, DATE '2021-11-14', 'bj_pre_20211115', 'official_bse_code_mapping_seed', 3, TRUE, 'Official BSE new-old code mapping seed'),
    ('bj920476', '920476.BJ', 'bj430476', '430476.BJ', NULL, DATE '2021-11-14', 'bj_pre_20211115', 'official_bse_code_mapping_seed', 3, TRUE, 'Official BSE new-old code mapping seed'),
    ('bj920489', '920489.BJ', 'bj430489', '430489.BJ', NULL, DATE '2021-11-14', 'bj_pre_20211115', 'official_bse_code_mapping_seed', 3, TRUE, 'Official BSE new-old code mapping seed'),
    ('bj920879', '920879.BJ', 'bj830879', '830879.BJ', NULL, DATE '2021-11-14', 'bj_pre_20211115', 'official_bse_code_mapping_seed', 3, TRUE, 'Official BSE new-old code mapping seed'),
    ('bj920152', '920152.BJ', 'bj831152', '831152.BJ', NULL, DATE '2021-11-14', 'bj_pre_20211115', 'official_bse_code_mapping_seed', 3, TRUE, 'Official BSE new-old code mapping seed'),
    ('bj920478', '920478.BJ', 'bj430478', '430478.BJ', NULL, DATE '2021-11-14', 'bj_pre_20211115', 'official_bse_code_mapping_seed', 3, TRUE, 'Official BSE new-old code mapping seed'),
    ('bj920087', '920087.BJ', 'bj831087', '831087.BJ', NULL, DATE '2021-11-14', 'bj_pre_20211115', 'official_bse_code_mapping_seed', 3, TRUE, 'Official BSE new-old code mapping seed'),
    ('bj920974', '920974.BJ', 'bj830974', '830974.BJ', NULL, DATE '2021-11-14', 'bj_pre_20211115', 'official_bse_code_mapping_seed', 3, TRUE, 'Official BSE new-old code mapping seed'),
    ('bj920023', '920023.BJ', 'bj832023', '832023.BJ', NULL, DATE '2021-11-14', 'bj_pre_20211115', 'official_bse_code_mapping_seed', 3, TRUE, 'Official BSE new-old code mapping seed'),
    ('bj920799', '920799.BJ', 'bj873799', '873799.BJ', NULL, DATE '2021-11-14', 'bj_pre_20211115', 'official_bse_code_mapping_seed', 3, TRUE, 'Official BSE new-old code mapping seed'),
    ('bj920961', '920961.BJ', 'bj873961', '873961.BJ', NULL, DATE '2021-11-14', 'bj_pre_20211115', 'official_bse_code_mapping_seed', 3, TRUE, 'Official BSE new-old code mapping seed')
ON CONFLICT (current_symbol, historical_symbol, phase_type) DO UPDATE SET
    current_ts_code = EXCLUDED.current_ts_code,
    historical_ts_code = EXCLUDED.historical_ts_code,
    phase_start = EXCLUDED.phase_start,
    phase_end = EXCLUDED.phase_end,
    mapping_source = EXCLUDED.mapping_source,
    mapping_confidence = EXCLUDED.mapping_confidence,
    is_active = EXCLUDED.is_active,
    notes = EXCLUDED.notes,
    updated_at = NOW();

CREATE TABLE IF NOT EXISTS public.pams_ohlcv_daily_v2 (
    symbol VARCHAR(20) NOT NULL,
    ts_code VARCHAR(12) NOT NULL,
    market VARCHAR(10) NOT NULL DEFAULT 'CN_A',
    market_phase VARCHAR(24) NOT NULL DEFAULT 'sh',
    trade_date DATE NOT NULL,
    row_status VARCHAR(24) NOT NULL,
    is_suspended BOOLEAN NOT NULL,
    pre_close NUMERIC(12,4) NOT NULL,
    pre_close_source TEXT NOT NULL DEFAULT 'daily_pre_close',
    pre_close_confidence SMALLINT NOT NULL DEFAULT 3,
    open NUMERIC(12,4) NOT NULL,
    high NUMERIC(12,4) NOT NULL,
    low NUMERIC(12,4) NOT NULL,
    close NUMERIC(12,4) NOT NULL,
    volume BIGINT NOT NULL,
    turnover NUMERIC(18,2) NOT NULL,
    adj_factor NUMERIC(14,6) NOT NULL,
    adj_factor_source TEXT NOT NULL DEFAULT 'tushare_adj_factor',
    adj_factor_confidence SMALLINT NOT NULL DEFAULT 3,
    limit_up NUMERIC(12,4) NOT NULL,
    limit_down NUMERIC(12,4) NOT NULL,
    turnover_rate DOUBLE PRECISION NOT NULL,
    turnover_rate_source TEXT NOT NULL DEFAULT 'tushare_daily_basic',
    turnover_rate_confidence SMALLINT NOT NULL DEFAULT 3,
    turnover_rate_f DOUBLE PRECISION,
    volume_ratio DOUBLE PRECISION,
    float_share DOUBLE PRECISION,
    free_share DOUBLE PRECISION,
    circ_mv DOUBLE PRECISION,
    source_daily_present BOOLEAN NOT NULL DEFAULT FALSE,
    source_adj_factor_present BOOLEAN NOT NULL DEFAULT FALSE,
    source_daily_basic_present BOOLEAN NOT NULL DEFAULT FALSE,
    source_stk_limit_present BOOLEAN NOT NULL DEFAULT FALSE,
    source_suspend_present BOOLEAN NOT NULL DEFAULT FALSE,
    build_run_id TEXT NOT NULL,
    build_version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (symbol, market, trade_date),
    UNIQUE (ts_code, trade_date)
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'chk_pams_ohlcv_daily_v2_row_status'
    ) THEN
        ALTER TABLE public.pams_ohlcv_daily_v2
            ADD CONSTRAINT chk_pams_ohlcv_daily_v2_row_status
            CHECK (row_status IN ('traded', 'suspended_confirmed', 'delist_tail_confirmed', 'synthetic_gap_fill', 'source_unresolved'));
    END IF;
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'chk_pams_ohlcv_daily_v2_market_phase'
    ) THEN
        ALTER TABLE public.pams_ohlcv_daily_v2
            ADD CONSTRAINT chk_pams_ohlcv_daily_v2_market_phase
            CHECK (market_phase IN ('sh', 'sz', 'bj_pre_20211115', 'bj_post_20211115'));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_pams_ohlcv_daily_v2_trade_date
    ON public.pams_ohlcv_daily_v2 (trade_date);
CREATE INDEX IF NOT EXISTS idx_pams_ohlcv_daily_v2_symbol_market
    ON public.pams_ohlcv_daily_v2 (symbol, market);
CREATE INDEX IF NOT EXISTS idx_pams_ohlcv_daily_v2_build_run_id
    ON public.pams_ohlcv_daily_v2 (build_run_id);

CREATE TABLE IF NOT EXISTS public.pit_stock_moneyflow_v2 (
    symbol TEXT NOT NULL,
    trade_date DATE NOT NULL,
    buy_sm_vol BIGINT,
    sell_sm_vol BIGINT,
    buy_md_vol BIGINT,
    sell_md_vol BIGINT,
    buy_lg_vol BIGINT,
    sell_lg_vol BIGINT,
    buy_elg_vol BIGINT,
    sell_elg_vol BIGINT,
    net_mf_vol BIGINT,
    buy_sm_amount DOUBLE PRECISION,
    sell_sm_amount DOUBLE PRECISION,
    buy_md_amount DOUBLE PRECISION,
    sell_md_amount DOUBLE PRECISION,
    buy_lg_amount DOUBLE PRECISION,
    sell_lg_amount DOUBLE PRECISION,
    buy_elg_amount DOUBLE PRECISION,
    sell_elg_amount DOUBLE PRECISION,
    net_mf_amount DOUBLE PRECISION,
    source_moneyflow_present BOOLEAN NOT NULL DEFAULT FALSE,
    net_fields_present BOOLEAN NOT NULL DEFAULT FALSE,
    source TEXT NOT NULL DEFAULT 'tushare_moneyflow',
    build_run_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (symbol, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_pit_stock_moneyflow_v2_trade_date
    ON public.pit_stock_moneyflow_v2 (trade_date DESC);
CREATE INDEX IF NOT EXISTS idx_pit_stock_moneyflow_v2_build_run_id
    ON public.pit_stock_moneyflow_v2 (build_run_id);

CREATE TABLE IF NOT EXISTS public.pit_stock_moneyflow_v2_whitelist_daily (
    trade_date DATE NOT NULL,
    build_run_id TEXT NOT NULL,
    row_coverage_ratio DOUBLE PRECISION NOT NULL,
    net_amount_coverage_ratio DOUBLE PRECISION NOT NULL,
    required_row_coverage_ratio DOUBLE PRECISION NOT NULL DEFAULT 0.95,
    required_net_coverage_ratio DOUBLE PRECISION NOT NULL DEFAULT 0.90,
    allow_in_research BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (trade_date, build_run_id)
);

CREATE TABLE IF NOT EXISTS public.pams_ohlcv_daily_v2_audit_daily (
    trade_date DATE NOT NULL,
    build_run_id TEXT NOT NULL,
    eligible_symbol_count INTEGER NOT NULL DEFAULT 0,
    raw_daily_count INTEGER NOT NULL DEFAULT 0,
    v2_count INTEGER NOT NULL DEFAULT 0,
    daily_basic_join_count INTEGER NOT NULL DEFAULT 0,
    moneyflow_join_count INTEGER NOT NULL DEFAULT 0,
    eligible_missing_daily_count INTEGER NOT NULL DEFAULT 0,
    daily_basic_missing_count INTEGER NOT NULL DEFAULT 0,
    moneyflow_missing_count INTEGER NOT NULL DEFAULT 0,
    turnover_rate_f_null_count INTEGER NOT NULL DEFAULT 0,
    volume_ratio_null_count INTEGER NOT NULL DEFAULT 0,
    float_share_null_count INTEGER NOT NULL DEFAULT 0,
    free_share_null_count INTEGER NOT NULL DEFAULT 0,
    circ_mv_null_count INTEGER NOT NULL DEFAULT 0,
    v1_count INTEGER NOT NULL DEFAULT 0,
    v2_minus_v1 INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (trade_date, build_run_id)
);

CREATE INDEX IF NOT EXISTS idx_pams_ohlcv_daily_v2_audit_daily_build_run_id
    ON public.pams_ohlcv_daily_v2_audit_daily (build_run_id);

CREATE TABLE IF NOT EXISTS public.pams_ohlcv_daily_v2_exceptions (
    id BIGSERIAL PRIMARY KEY,
    trade_date DATE,
    symbol TEXT,
    ts_code TEXT,
    issue_type TEXT NOT NULL,
    cause_class TEXT,
    issue_detail TEXT,
    source_table TEXT,
    build_run_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pams_ohlcv_daily_v2_exceptions_trade_date
    ON public.pams_ohlcv_daily_v2_exceptions (trade_date);
CREATE INDEX IF NOT EXISTS idx_pams_ohlcv_daily_v2_exceptions_issue_type
    ON public.pams_ohlcv_daily_v2_exceptions (issue_type);
CREATE INDEX IF NOT EXISTS idx_pams_ohlcv_daily_v2_exceptions_build_run_id
    ON public.pams_ohlcv_daily_v2_exceptions (build_run_id);

DROP VIEW IF EXISTS public.pams_ohlcv_daily_v2_runtime;

CREATE VIEW public.pams_ohlcv_daily_v2_runtime AS
SELECT
    symbol,
    ts_code,
    market,
    market_phase,
    trade_date,
    row_status,
    is_suspended,
    pre_close,
    pre_close_source,
    pre_close_confidence,
    open,
    high,
    low,
    close,
    volume,
    turnover,
    adj_factor,
    adj_factor_source,
    adj_factor_confidence,
    limit_up,
    limit_down,
    turnover_rate,
    turnover_rate_source,
    turnover_rate_confidence,
    turnover_rate_f,
    volume_ratio,
    float_share,
    free_share,
    circ_mv,
    source_daily_present,
    source_adj_factor_present,
    source_daily_basic_present,
    source_stk_limit_present,
    source_suspend_present,
    build_run_id,
    build_version,
    created_at,
    updated_at
FROM public.pams_ohlcv_daily_v2
WHERE row_status IN ('traded', 'suspended_confirmed')
  AND pre_close_confidence >= 1
  AND adj_factor_confidence >= 1
  AND (turnover_rate_confidence >= 1 OR is_suspended = TRUE);

COMMIT;
