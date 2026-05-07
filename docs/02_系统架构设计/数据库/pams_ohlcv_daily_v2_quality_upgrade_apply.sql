BEGIN;

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

ALTER TABLE public.pams_ohlcv_daily_v2
    ADD COLUMN IF NOT EXISTS market_phase VARCHAR(24);

ALTER TABLE public.pams_ohlcv_daily_v2
    ALTER COLUMN row_status TYPE VARCHAR(24);

ALTER TABLE public.pams_ohlcv_daily_v2
    ADD COLUMN IF NOT EXISTS pre_close_source TEXT;

ALTER TABLE public.pams_ohlcv_daily_v2
    ADD COLUMN IF NOT EXISTS pre_close_confidence SMALLINT;

ALTER TABLE public.pams_ohlcv_daily_v2
    ADD COLUMN IF NOT EXISTS adj_factor_source TEXT;

ALTER TABLE public.pams_ohlcv_daily_v2
    ADD COLUMN IF NOT EXISTS adj_factor_confidence SMALLINT;

ALTER TABLE public.pams_ohlcv_daily_v2
    ADD COLUMN IF NOT EXISTS turnover_rate_confidence SMALLINT;

ALTER TABLE public.pams_ohlcv_daily_v2_exceptions
    ADD COLUMN IF NOT EXISTS cause_class TEXT;

ALTER TABLE public.pams_ohlcv_daily_v2
    DROP CONSTRAINT IF EXISTS chk_pams_ohlcv_daily_v2_row_status;

UPDATE public.pams_ohlcv_daily_v2
SET
    market_phase = CASE
        WHEN symbol LIKE 'bj%' AND trade_date < DATE '2021-11-15' THEN 'bj_pre_20211115'
        WHEN symbol LIKE 'bj%' THEN 'bj_post_20211115'
        WHEN symbol LIKE 'sh%' THEN 'sh'
        ELSE 'sz'
    END,
    row_status = CASE
        WHEN row_status = 'suspended' AND source_suspend_present THEN 'suspended_confirmed'
        WHEN row_status = 'suspended' THEN 'source_unresolved'
        ELSE row_status
    END,
    pre_close_source = CASE
        WHEN pre_close = 0 THEN 'imputed_zero'
        WHEN row_status = 'traded' THEN 'daily_pre_close'
        WHEN source_suspend_present THEN 'prev_close_carry'
        ELSE 'prev_close_carry'
    END,
    pre_close_confidence = CASE
        WHEN pre_close = 0 THEN 0
        WHEN row_status = 'traded' THEN 3
        WHEN source_suspend_present THEN 2
        ELSE 1
    END,
    adj_factor_source = CASE
        WHEN source_adj_factor_present THEN 'tushare_adj_factor'
        WHEN COALESCE(adj_factor, 1) = 1 THEN 'default_1'
        ELSE 'prev_adj_factor_carry'
    END,
    adj_factor_confidence = CASE
        WHEN source_adj_factor_present THEN 3
        WHEN COALESCE(adj_factor, 1) = 1 THEN 0
        ELSE 1
    END,
    turnover_rate_source = CASE
        WHEN source_daily_basic_present THEN 'tushare_daily_basic'
        WHEN row_status = 'suspended' AND source_suspend_present THEN 'suspended_zero'
        WHEN row_status = 'suspended_confirmed' THEN 'suspended_zero'
        WHEN COALESCE(turnover_rate, 0) = 0 THEN 'imputed_zero'
        ELSE COALESCE(turnover_rate_source, 'derived_formula')
    END,
    turnover_rate_confidence = CASE
        WHEN source_daily_basic_present THEN 3
        WHEN row_status = 'suspended' AND source_suspend_present THEN 3
        WHEN row_status = 'suspended_confirmed' THEN 3
        WHEN COALESCE(turnover_rate, 0) = 0 THEN 0
        ELSE 1
    END
WHERE
    market_phase IS NULL
    OR pre_close_source IS NULL
    OR pre_close_confidence IS NULL
    OR adj_factor_source IS NULL
    OR adj_factor_confidence IS NULL
    OR turnover_rate_confidence IS NULL
    OR row_status = 'suspended';

UPDATE public.pams_ohlcv_daily_v2_exceptions
SET cause_class = CASE
    WHEN issue_type = 'eligible_no_source' AND symbol LIKE 'bj%' AND trade_date < DATE '2021-11-15' THEN 'mapping_failure'
    WHEN issue_type = 'eligible_no_source' THEN 'missing_in_all_sources'
    WHEN issue_type IN ('raw_daily_field_missing', 'raw_only_moneyflow', 'hard_field_null_after_build') THEN 'build_rule_rejected'
    WHEN issue_type IN ('pre_close_imputed_zero', 'turnover_rate_imputed_zero', 'limit_price_imputed_anchor', 'adj_factor_default_1') THEN 'source_present_low_confidence_fill'
    ELSE cause_class
END
WHERE cause_class IS NULL;

ALTER TABLE public.pams_ohlcv_daily_v2
    ALTER COLUMN market_phase SET NOT NULL,
    ALTER COLUMN market_phase SET DEFAULT 'sh',
    ALTER COLUMN pre_close_source SET NOT NULL,
    ALTER COLUMN pre_close_source SET DEFAULT 'daily_pre_close',
    ALTER COLUMN pre_close_confidence SET NOT NULL,
    ALTER COLUMN pre_close_confidence SET DEFAULT 3,
    ALTER COLUMN adj_factor_source SET NOT NULL,
    ALTER COLUMN adj_factor_source SET DEFAULT 'tushare_adj_factor',
    ALTER COLUMN adj_factor_confidence SET NOT NULL,
    ALTER COLUMN adj_factor_confidence SET DEFAULT 3,
    ALTER COLUMN turnover_rate_confidence SET NOT NULL,
    ALTER COLUMN turnover_rate_confidence SET DEFAULT 3;

ALTER TABLE public.pams_ohlcv_daily_v2
    ADD CONSTRAINT chk_pams_ohlcv_daily_v2_row_status
    CHECK (row_status IN ('traded', 'suspended_confirmed', 'synthetic_gap_fill', 'source_unresolved'));

ALTER TABLE public.pams_ohlcv_daily_v2
    DROP CONSTRAINT IF EXISTS chk_pams_ohlcv_daily_v2_market_phase;

ALTER TABLE public.pams_ohlcv_daily_v2
    ADD CONSTRAINT chk_pams_ohlcv_daily_v2_market_phase
    CHECK (market_phase IN ('sh', 'sz', 'bj_pre_20211115', 'bj_post_20211115'));

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
