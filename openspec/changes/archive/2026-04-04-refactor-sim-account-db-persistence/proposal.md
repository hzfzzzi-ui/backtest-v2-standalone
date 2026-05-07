## Why

`sim_account` 现在已经被收成统一域服务，但正式持久化仍停留在 `outputs/ops/sim_account/*` 文件域。只要账户主数据、持仓快照、现金账本和同步日志还没有进入事务域数据库对象，`sim_account` 就仍然是“边界正确但落点未换”的过渡态。

## What Changes

- 将 `sim_account` 的正式持久化切到业务事务域数据库对象，包括账户主数据、持仓快照、现金账本、同步日志。
- 保持 `reconcile` 为派生分析结果，只把摘要/引用纳入正式数据库对象。
- 将 `outputs/ops/sim_account/*` 明确降级为迁移期 compat 路径，并定义退出条件。
- 固定事务域中 `cash_ledger` 与 `sync_logs` 的正式对象边界。

## Capabilities

### New Capabilities
- `sim-account-db-persistence`: 定义 `sim_account` 在业务事务域中的正式数据库对象、派生摘要与 compat 退出约束。

### Modified Capabilities
- `sim-account-auto-sync`: 正式写入账户运营对象，而不是长期依赖文件产物。
- `sim-account-holdings-sync`: 正式写入持仓快照对象。
- `position-aware-reconcile-run`: `reconcile` 降级为派生摘要/引用，不再充当底层真相。
- `research-db-structure-governance`: 业务事务域新增 `sim_account` 正式对象定位。

## Impact

- 影响模块：`backend/core/services/sim_account_*`、账户同步、现金账本、reconcile 摘要、事务域数据库访问层。
- 影响数据：账户主数据、持仓快照、现金账本、同步日志、reconcile 摘要。
- 风险：文件 compat 与数据库对象并行期间可能出现状态漂移。
