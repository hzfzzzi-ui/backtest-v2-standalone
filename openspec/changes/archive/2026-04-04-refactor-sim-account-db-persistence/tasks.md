## 1. 正式对象定义

- [x] 1.1 定义 `accounts / holdings_snapshots / cash_ledger / sync_logs` 的正式数据库对象边界。（DoD: specs 与数据库治理文档一致；验证: `openspec validate refactor-sim-account-db-persistence` 通过；风险: 账户运营对象再次混层）
- [x] 1.2 固定 `cash_ledger` 与 `sync_logs` 为同一账户运营子域中的两类正式对象。（DoD: spec 场景可区分现金变动与同步事件；验证: delta spec 覆盖两类场景；风险: 日志再次被并入账本）

## 2. sim_account 正式持久化迁移

- [x] 2.1 将 `sim-account-holdings-sync` 正式收口到持仓快照对象。（DoD: spec 明确持仓快照为正式写入面；验证: 场景覆盖快照写入与读取；风险: 旧 latest/history 文件继续被当主真相）
- [x] 2.2 将 `sim-account-auto-sync` 正式收口到现金账本与同步日志对象。（DoD: spec 明确自动同步写入对象；验证: 场景覆盖同步结束、现金更新；风险: 现金与同步状态脱钩）

## 3. reconcile 与 compat

- [x] 3.1 将 `position-aware-reconcile-run` 明确降级为派生摘要/引用。（DoD: spec 不再把完整 reconcile payload 当底层真相；验证: reconcile 摘要场景完整；风险: 旧工具链仍依赖完整 payload）
- [x] 3.2 明确 `outputs/ops/sim_account/*` 的 compat 退出条件与回退顺序。（DoD: design/tasks 有清晰退出门槛；验证: 回退步骤可读；风险: compat 退出过早）

