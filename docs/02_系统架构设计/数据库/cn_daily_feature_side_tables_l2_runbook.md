# CN Daily Feature Side Tables Runbook

## 目标

新增三条托管链路：
- `pit_stock_daily_basic` 回填 / 增量同步
- `pit_stock_moneyflow` 回填 / 增量同步
- `pit_stock_feature_coverage` 覆盖率审计

本轮只补数据落地与覆盖率审计，不改变 `pams_ohlcv_daily` 主表语义，也不接入 baseline 默认消费路径。

## 建表

执行：

```powershell
docker exec -i pams-postgres psql -U pams -d pams < docs/db/cn_daily_feature_side_tables_l2_apply.sql
```

回退：

```powershell
docker exec -i pams-postgres psql -U pams -d pams < docs/db/cn_daily_feature_side_tables_l2_rollback.sql
```

## 最小 Smoke

```powershell
docker exec backtest-v2-standalone python -m backend.cli data_refresh --target pit_stock_daily_basic -- --start 2026-03-20 --end 2026-03-20 --apply
docker exec backtest-v2-standalone python -m backend.cli data_refresh --target pit_stock_moneyflow -- --start 2026-03-20 --end 2026-03-20 --apply
docker exec backtest-v2-standalone python -m backend.cli data_refresh --target pit_stock_feature_coverage -- --start 2026-03-20 --end 2026-03-20
```

## 历史回填

推荐分段执行，避免单次任务过长：

```powershell
docker exec backtest-v2-standalone python -m backend.cli data_refresh --target pit_stock_daily_basic -- --start 2007-01-04 --end 2012-12-31 --apply
docker exec backtest-v2-standalone python -m backend.cli data_refresh --target pit_stock_daily_basic -- --start 2013-01-01 --end 2018-12-31 --apply
docker exec backtest-v2-standalone python -m backend.cli data_refresh --target pit_stock_daily_basic -- --start 2019-01-01 --end 2026-03-20 --apply
```

```powershell
docker exec backtest-v2-standalone python -m backend.cli data_refresh --target pit_stock_moneyflow -- --start 2007-01-04 --end 2012-12-31 --apply
docker exec backtest-v2-standalone python -m backend.cli data_refresh --target pit_stock_moneyflow -- --start 2013-01-01 --end 2018-12-31 --apply
docker exec backtest-v2-standalone python -m backend.cli data_refresh --target pit_stock_moneyflow -- --start 2019-01-01 --end 2026-03-20 --apply
```

如果不传 `--end`，脚本按最新可得交易日收口。

## 覆盖率审计

全量回填完成后必须立即执行：

```powershell
docker exec backtest-v2-standalone python -m backend.cli data_refresh --target pit_stock_feature_coverage -- --start 2007-01-04 --end 2026-03-20
```

审计产物至少检查：
- `summary.json`
- `pit_stock_feature_coverage_per_trade_date.csv`
- `pit_stock_daily_basic_missing_sample.csv`
- `pit_stock_daily_basic_excess_sample.csv`
- `pit_stock_moneyflow_missing_sample.csv`
- `pit_stock_moneyflow_excess_sample.csv`

## 验证

```powershell
docker exec pams-postgres psql -U pams -d pams -c "SELECT COUNT(*), MIN(trade_date), MAX(trade_date) FROM pit_stock_daily_basic;"
docker exec pams-postgres psql -U pams -d pams -c "SELECT COUNT(*), MIN(trade_date), MAX(trade_date) FROM pit_stock_moneyflow;"
docker exec pams-postgres psql -U pams -d pams -c "SELECT COUNT(*), MIN(trade_date), MAX(trade_date) FROM pams_ohlcv_daily WHERE market = 'CN_A';"
```
