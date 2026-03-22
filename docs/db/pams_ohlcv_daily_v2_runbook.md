# `pams_ohlcv_daily_v2` Runbook

## 目标

本 runbook 用于：
- 建表与回滚
- 单段 smoke
- `v2` 全历史 raw/main/moneyflow/audit 正式回填
- 宿主机侧查看 `exit_code / heartbeat / OOMKilled / status`

## 建表

执行：
```powershell
docker exec -i pams-postgres psql -U pams -d pams < docs/db/pams_ohlcv_daily_v2_apply.sql
```

回滚：
```powershell
docker exec -i pams-postgres psql -U pams -d pams < docs/db/pams_ohlcv_daily_v2_rollback.sql
```

## Smoke

单日 smoke 仍可直接走容器内统一 CLI：
```powershell
docker exec backtest-v2-standalone python -m backend.cli data_refresh --target security_master -- --apply
docker exec backtest-v2-standalone python -m backend.cli data_refresh --target pams_ohlcv_daily_v2_raw -- --start 2026-03-16 --end 2026-03-16 --apply
docker exec backtest-v2-standalone python -m backend.cli data_refresh --target pams_ohlcv_daily_v2 -- --start 2026-03-16 --end 2026-03-16 --apply
docker exec backtest-v2-standalone python -m backend.cli data_refresh --target pit_stock_moneyflow_v2 -- --start 2026-03-16 --end 2026-03-16 --apply
docker exec backtest-v2-standalone python -m backend.cli data_refresh --target pams_ohlcv_daily_v2_audit -- --start 2026-03-16 --end 2026-03-16 --apply
```

## 单段回填

需要单独调试某一段时，优先走独立 worker：
```powershell
docker compose --profile worker run --rm backtest-v2-worker python -m backend.cli data_refresh --target pams_ohlcv_daily_v2_raw -- --start 2007-01-04 --end 2012-12-31 --apply
docker compose --profile worker run --rm backtest-v2-worker python -m backend.cli data_refresh --target pams_ohlcv_daily_v2 -- --start 2007-01-04 --end 2012-12-31 --apply
docker compose --profile worker run --rm backtest-v2-worker python -m backend.cli data_refresh --target pit_stock_moneyflow_v2 -- --start 2007-01-04 --end 2012-12-31 --apply
docker compose --profile worker run --rm backtest-v2-worker python -m backend.cli data_refresh --target pams_ohlcv_daily_v2_audit -- --start 2007-01-04 --end 2026-03-16 --apply
```

## 正式全量回填

禁止再用临时 `docker exec -d` 长命令。正式全量回填使用宿主机 launcher：
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\ops\run_pams_ohlcv_daily_v2_full_backfill.ps1 -Apply
```

只跑子集：
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\ops\run_pams_ohlcv_daily_v2_full_backfill.ps1 -Start 2007-01-04 -End 2012-12-31 -Apply
```

定向 symbol smoke：
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\ops\run_pams_ohlcv_daily_v2_full_backfill.ps1 -Start 2026-03-16 -End 2026-03-16 -SymbolsCsv sh600000,sz000001 -Apply
```

## 状态文件

launcher 运行后会在 `outputs/ops/<run_name>/` 下生成：
- `launcher_status.json`
- `worker_container_state.json`
- `worker_container.log`
- `worker_container_name.txt`
- `exit_code.txt`

容器内 full-backfill runner 会继续写：
- `status.json`
- `failure.json`（失败时）
- `heartbeat.json`
- `current_step.txt`
- 各 step 子目录下的 `summary.json`

### 关键判断

- `exit_code.txt` 不存在：launcher 自身未完整收尾
- `exit_code.txt = 0`：worker 进程正常退出
- `launcher_status.json.status = failed_oom`：worker 容器被 OOM kill
- `heartbeat.json.updated_at` 长时间不变：优先查当前 step 是否卡住
- `worker_container_state.json.OOMKilled = true`：本次失败根因是容器级内存杀掉

## 验证

```powershell
docker exec pams-postgres psql -U pams -d pams -c "SELECT COUNT(*), MIN(trade_date), MAX(trade_date) FROM pams_ohlcv_daily_v2;"
docker exec pams-postgres psql -U pams -d pams -c "SELECT COUNT(*), MIN(trade_date), MAX(trade_date) FROM pit_stock_moneyflow_v2;"
docker exec pams-postgres psql -U pams -d pams -c "SELECT COUNT(*), MIN(trade_date), MAX(trade_date) FROM pams_ohlcv_daily_v2_audit_daily;"
docker exec pams-postgres psql -U pams -d pams -c "SELECT issue_type, COUNT(*) FROM pams_ohlcv_daily_v2_exceptions GROUP BY 1 ORDER BY 1;"
```

## 当前约束

- 正式全量回填必须跑在 `backtest-v2-worker`
- `backtest-v2-standalone` 只保留 API 与短任务
- `moneyflow` 仍是侧表，不进入 `pams_ohlcv_daily_v2` 主表成功定义
