# 模拟账户持仓每日自动同步说明

## 0. 文档定位

本文档描述模拟账户持仓自动同步链路的迁移期运行约束。

它不再定义数据库正式边界；数据库正式边界以 [数据库架构设计](../数据库/数据库架构设计.md) 为准。当前系统已明确：

- 市场数据正式消费入口是 `canonical_market`
- `pams_ohlcv_daily` 长期目标是完全退役
- `reconcile` 是派生分析结果，不是事务域底层真相

## 1. 目的

这条链路用于把外部模拟盘导出的持仓 `JSON` 自动导入系统内部的模拟账户状态，并在必要时触发一次 position-aware `reconcile` 派生分析。

正式目标是：

- 把账户主数据、持仓快照、交易生命周期、现金账本、同步/对账日志收回数据库
- 不再把 `outputs/ops/sim_account/*` 当作长期主真相路径

## 2. 环境变量

- `SIM_ACCOUNT_AUTO_SYNC_ENABLED`
  - `true/false`
  - 未配置时默认按 `SIM_ACCOUNT_AUTO_SYNC_SOURCE_PATH` 是否存在决定；更稳定的做法是显式写成 `true`
- `SIM_ACCOUNT_AUTO_SYNC_SOURCE_PATH`
  - 持仓导出 `JSON` 文件路径
  - 可以是绝对路径，也可以是相对当前工作目录的路径
- `SIM_ACCOUNT_AUTO_SYNC_ACCOUNT_ID`
  - 可选
  - 默认 `paper_a_share_main`

## 3. 输入 JSON 格式

导入文件复用当前 holdings snapshot 输入格式，至少包括：

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
- `sellable_qty` 必须位于 `0 ~ qty`
- `cash` 必须大于等于 `0`
- 如文件内包含 `account_id`，当前实现仍允许被 `SIM_ACCOUNT_AUTO_SYNC_ACCOUNT_ID` 覆盖

## 4. 正式运行边界

当前正式边界固定为：

- 市场数据刷新必须基于统一市场数据访问层与 `canonical_market`
- 自动同步负责“账户当前状态真相”导入
- `reconcile` 只作为派生分析结果存在
- 详细派生产物可以继续落文件，但数据库只保留摘要与引用

因此：

- 自动同步不再以 `pams_ohlcv_daily` 为默认前置口径
- 不再把 `outputs/ops/sim_account/*` 定义为长期主真相路径

## 5. 每日调度顺序

当前正式建议顺序为：

1. 通过统一市场数据访问层确认 `canonical_market` 所需市场数据已更新到目标交易日
2. 读取外部模拟盘持仓 `JSON`
3. 写入账户持仓快照到业务事务域数据库
4. 写入现金账本与同步/对账日志
5. 若 `trade_date` 与本次目标交易日一致，则触发一次 `reconcile` 派生分析
6. 将 `reconcile` 摘要与引用写入数据库，详细产物可继续保留为文件

不再把以下旧顺序写为正式口径：

1. 刷新 `pams_ohlcv_daily`
2. 刷新 `pit_index_daily`
3. 刷新 `csi800_pit`

这些对象属于历史实现细节，不再是当前文档中的正式主路径表达。

## 6. 数据落点

### 6.1 正式数据库对象

长期正式对象应收敛为：

- 账户主数据
- 当前持仓快照
- `transactions` 生命周期主表
- 现金账本
- 同步/对账日志
- `reconcile` 摘要与引用

### 6.2 迁移期文件产物

当前仍可能存在的文件产物包括：

- `outputs/ops/sim_account/<account_id>/holdings/latest.json`
- `outputs/ops/sim_account/<account_id>/holdings/history/<snapshot_id>.json`
- `outputs/ops/sim_account/<account_id>/reconcile/latest.json`
- `outputs/ops/sim_account/<account_id>/reconcile/history/<reconcile_id>.json`
- `outputs/ops/sim_account/<account_id>/auto_sync_status.json`

这些路径当前只能视为：

- 迁移期镜像
- 调试与回溯辅助产物
- 派生分析明细文件

它们不再被定义为正式事务真相。

### 6.3 compat 退出条件

`outputs/ops/sim_account/*` 退出迁移期 compat 前，至少必须同时满足：

1. `sim_account` 主服务已经不再把这些文件路径当作正式主读路径
2. 桌面端与移动端都改为读取账户运营域对象或 `reconcile summary`
3. 详细 `reconcile payload` 已明确只承担派生分析职责，不再承担同步真相职责
4. 已完成一轮“账户运营域为主、文件镜像为辅”的回归与回退验证

在这些条件满足之前，这些路径只能继续作为 compat 镜像存在，不得扩张为新的长期接口。

## 7. `reconcile` 定位

`reconcile` 当前正式定位是：

- 基于账户状态和实验真相运行出来的派生分析结果
- 不是账户事务底层真相
- 不应与持仓快照、交易生命周期、现金账本混在同一正式对象层

因此：

- 数据库中只保留 `reconcile` 摘要和引用
- 详细 `action_sheet / diagnostics / execution_intent` 可继续作为外部产物保留

## 8. 手动触发

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

以上命令仅代表当前实现入口，不改变本文档定义的正式边界。

## 9. 回退原则

### 回退自动同步

1. 关闭：
   - `SIM_ACCOUNT_AUTO_SYNC_ENABLED=false`
   - 或删除 `SIM_ACCOUNT_AUTO_SYNC_SOURCE_PATH`
2. 重启服务
3. 保留账户运营域写入，必要时仅把文件镜像恢复成主读
4. 若要回放旧镜像，先停自动同步，再用历史快照覆盖当前 compat 文件

### 回退到旧快照

若仍需使用历史文件镜像回退，可继续用：

- `holdings/history/<snapshot_id>.json` 覆盖 `holdings/latest.json`
- `reconcile/history/<reconcile_id>.json` 覆盖 `reconcile/latest.json`

但这只代表迁移期兼容操作，不应被误写成长期正式数据库边界。
