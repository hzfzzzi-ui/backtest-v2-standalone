## Why

当前 `sim_account` 相关正式对象仍散落在数据库、`outputs/ops/sim_account/*` 文件产物以及运行时服务内部。持仓快照、现金池刷新、同步/对账日志与 `reconcile` 建议面长期混在一起，导致：

- 账户运营真相与派生分析结果边界不清
- 事务域数据库与文件系统长期并存
- 后续桌面执行、移动端读取和账户回写都缺少稳定底座

文档层已经收口：

- 业务事务域应正式覆盖账户主数据、当前持仓快照、交易/成交真相、账户运营日志
- 现金账本与对账日志应成为两个正式对象，但归于同一账户运营子域
- `reconcile` 只保留摘要/引用，不再升格为底层真相

## What Changes

- 新增 `account ops domain` 正式能力，定义账户、持仓快照、现金账本、同步/对账日志的正式边界。
- 将 `sim-account-auto-sync` 和 `sim-account-holdings-sync` 的正式真相从文件产物收回事务域数据库。
- 将 `position-aware-reconcile-run` 收口为派生分析结果，仅保留摘要和引用进入数据库。
- 为后续事务域拆库与桌面执行回写提供稳定主对象。

## Capabilities

### New Capabilities
- `account-ops-domain`: 定义事务域中的账户主数据、持仓快照、现金账本和同步/对账日志。

### Modified Capabilities
- `sim-account-auto-sync`: 自动同步正式写入账户运营子域，不再长期依赖 `outputs/ops/sim_account/*` 作为主真相。
- `sim-account-holdings-sync`: 持仓同步正式落到持仓快照与账户运营日志。
- `position-aware-reconcile-run`: reconcile 降级为派生分析能力，只保留摘要/引用进入数据库。

## Impact

- 主要影响模块：
  - `backend/core/services/sim_account_reconcile_service.py`
  - `backend/core/services` 中 sim account 同步、快照、现金相关服务
  - `docs/02_系统架构设计/前端与移动端/sim_account_auto_sync.md`
- 主要风险：
  - 旧文件协议与数据库对象并存时可能出现双重真相
  - `reconcile` 从底层真相降级后，需要避免上游继续依赖完整 payload
- 主要验证：
  - 持仓快照与现金账本回归
  - 同步/对账日志回归
  - reconcile 摘要索引回归
