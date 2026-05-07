-- Runtime compatibility view for baseline consumption.
-- Canonical truth remains in pams_ohlcv_daily_v2.

DROP VIEW IF EXISTS pams_ohlcv_daily_v2_runtime;

CREATE VIEW pams_ohlcv_daily_v2_runtime AS
SELECT
    symbol,
    ts_code,
    market,
    market_phase,
    trade_date,
    row_status,
    is_suspended,
    pre_close,
    open,
    high,
    low,
    close,
    volume,
    turnover,
    adj_factor,
    limit_up,
    limit_down,
    turnover_rate,
    turnover_rate_f,
    volume_ratio,
    float_share,
    free_share,
    circ_mv,
    pre_close_source,
    pre_close_confidence,
    adj_factor_source,
    adj_factor_confidence,
    turnover_rate_source,
    turnover_rate_confidence,
    source_daily_present,
    source_adj_factor_present,
    source_daily_basic_present,
    source_stk_limit_present,
    source_suspend_present,
    build_run_id,
    build_version,
    created_at,
    updated_at
FROM pams_ohlcv_daily_v2
WHERE row_status IN ('traded', 'suspended_confirmed')
  AND pre_close_confidence >= 1
  AND adj_factor_confidence >= 1
  AND (turnover_rate_confidence >= 1 OR is_suspended = TRUE);
