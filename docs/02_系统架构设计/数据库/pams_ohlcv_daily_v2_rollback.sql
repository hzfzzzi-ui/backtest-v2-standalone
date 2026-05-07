BEGIN;

DROP TABLE IF EXISTS public.pams_ohlcv_daily_v2_exceptions;
DROP TABLE IF EXISTS public.pams_ohlcv_daily_v2_audit_daily;
DROP TABLE IF EXISTS public.pit_stock_moneyflow_v2_whitelist_daily;
DROP TABLE IF EXISTS public.pit_stock_moneyflow_v2;
DROP TABLE IF EXISTS public.pams_ohlcv_daily_v2;

DROP TABLE IF EXISTS public.raw_tushare_moneyflow;
DROP TABLE IF EXISTS public.raw_tushare_stk_limit;
DROP TABLE IF EXISTS public.raw_tushare_suspend_d;
DROP TABLE IF EXISTS public.raw_tushare_daily_basic;
DROP TABLE IF EXISTS public.raw_tushare_adj_factor;
DROP TABLE IF EXISTS public.raw_tushare_daily;
DROP TABLE IF EXISTS public.raw_tushare_trade_cal;
DROP TABLE IF EXISTS public.raw_tushare_stock_basic;

COMMIT;
