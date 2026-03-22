# 模拟盘持仓每日自动同步说明

## 目的

这条链路用于把外部模拟盘导出的持仓 JSON 自动导入到系统内部的 sim account 快照，并在导入成功后自动重跑 position-aware reconcile。

当前不直接接券商 SDK。外部系统只需要按约定把最新持仓导出成一个 JSON 文件，系统每日 scheduler 会读取该文件。

## 环境变量

- `SIM_ACCOUNT_AUTO_SYNC_ENABLED`
  - `true/false`
  - 未配置时默认按 `SIM_ACCOUNT_AUTO_SYNC_SOURCE_PATH` 是否存在决定；最稳妥的做法是显式写成 `true`
- `SIM_ACCOUNT_AUTO_SYNC_SOURCE_PATH`
  - 持仓导出 JSON 文件路径
  - 可以是绝对路径，也可以是相对当前工作目录的路径
- `SIM_ACCOUNT_AUTO_SYNC_ACCOUNT_ID`
  - 可选
  - 默认 `paper_a_share_main`

## JSON 文件格式

导入文件复用现有 holdings snapshot 输入格式，至少包含：

```json
{
  "trade_date": "2026-03-16",
  "cash": 123456.78,
  "positions": [
    {
      "symbol": "600000.SH",
      "qty": 300,
      "sellable_qty": 200,
      "avg_cost": 10.5,
      "name": "浦发银行"
    },
    {
      "symbol": "000001.SZ",
      "qty": 100,
      "sellable_qty": 100,
      "avg_cost": 12.3,
      "name": "平安银行"
    }
  ]
}
```

说明：
- `symbol` 支持 `600000.SH`、`000001.SZ`、`sh600000`、`sz000001`
- `qty` 必须大于 `0`
- `sellable_qty` 必须在 `0 ~ qty`
- `cash` 必须大于等于 `0`
- 若文件内包含 `account_id`，当前实现也会被配置的 `SIM_ACCOUNT_AUTO_SYNC_ACCOUNT_ID` 覆盖

## 每日调度顺序

当前 scheduler 顺序为：

1. 刷新 `pams_ohlcv_daily`
2. 刷新 `pit_index_daily`
3. 刷新 `csi800_pit`
4. 读取模拟盘持仓 JSON
5. 写入 `holdings/latest.json`
6. 若 `trade_date` 与本次市场同步目标日一致，则自动重跑 reconcile

## 运行产物

### 持仓快照

- `outputs/ops/sim_account/<account_id>/holdings/latest.json`
- `outputs/ops/sim_account/<account_id>/holdings/history/<snapshot_id>.json`

### reconcile

- `outputs/ops/sim_account/<account_id>/reconcile/latest.json`
- `outputs/ops/sim_account/<account_id>/reconcile/history/<reconcile_id>.json`

### 自动同步状态

- `outputs/ops/sim_account/<account_id>/auto_sync_status.json`

状态字段至少包括：
- `status`
- `account_id`
- `source_path`
- `target_trade_date`
- `snapshot_id`
- `trade_date`
- `reconcile_id`
- `message`
- `error`
- `updated_at`

## 状态语义

- `disabled`
  - 未配置导入路径，或自动同步未启用
- `failed`
  - 文件缺失、JSON 非法、字段校验失败、reconcile 失败等
- `stale_input`
  - 文件导入成功，但 `trade_date` 早于本次市场同步目标日
  - 这时会写入新的 holdings snapshot，但不会生成新的 reconcile
- `success`
  - 持仓导入与 reconcile 都成功

## 手动触发命令

### 只补指数基准日线

```powershell
python backend/scripts/update_pit_index_daily.py --end 2026-03-16 --apply
```

### 手动跑一次自动持仓导入

```powershell
@'
from pathlib import Path
from backend.core.services.sim_account_auto_sync_service import run_auto_sync
payload = run_auto_sync(Path("outputs"), target_trade_date="2026-03-16")
print(payload)
'@ | python -
```

### 手动重建市场快照

```powershell
@'
from backend.core.services.market_snapshot_service import build_market_snapshot_artifacts
artifacts = build_market_snapshot_artifacts(trade_date="2026-03-16", bt_root="outputs")
print({"output_dir": str(artifacts.output_dir), "trade_date": artifacts.snapshot.get("trade_date")})
'@ | python -
```

## 失败回退

### 回退自动同步

1. 清空或关闭：
   - `SIM_ACCOUNT_AUTO_SYNC_ENABLED=false`
   - 或删除 `SIM_ACCOUNT_AUTO_SYNC_SOURCE_PATH`
2. 重启服务

### 回退到旧快照

用之前的 history 文件覆盖：

- `holdings/history/<snapshot_id>.json` -> `holdings/latest.json`
- 如需一起回退 trade sheet，再同步覆盖：
  - `reconcile/history/<reconcile_id>.json` -> `reconcile/latest.json`

## 注意事项

- 自动同步只负责“当前持仓真相”刷新，不替代 execution event 回写。
- 如果导入文件日期落后，mobile dashboard 会进入快照与 reconcile 不匹配或 stale 状态，这是刻意保护，不是前端错误。
- `pit_index_daily` 现在已接入每日 market data scheduler；若手机端仍显示旧指数告警，通常是旧 `market_snapshot.json` 还没重建。
