## Context

`sim_account` 文档已经把账户主数据、持仓快照、现金账本、同步日志定义为正式业务事务域对象，并把 `reconcile` 降成派生分析结果。但当前实现仍通过域服务把这些对象写回 `outputs/ops/sim_account/*`，因此还没有完成“文件域服务化 -> 数据库正式对象化”的关键一步。

## Goals / Non-Goals

**Goals:**
- 把 `accounts / holdings_snapshots / cash_ledger / sync_logs` 的正式落点切到业务事务域数据库对象。
- 保持 `cash_ledger` 与 `sync_logs` 分为两个正式对象，但归属同一账户运营子域。
- 保留 `reconcile_summary` 作为派生摘要索引，不恢复完整 payload 为主真相。
- 明确 compat 文件退出条件和回退路径。

**Non-Goals:**
- 不在本 change 中扩展真实券商接入。
- 不在本 change 中改变研究策略或 reconcile 计算逻辑。
- 不在本 change 中引入通知对象。

## Decisions

- 决策 1：账户主数据、持仓快照、现金账本、同步日志分别保持正式对象。
  原因：这几个对象职责清晰，继续合并只会让账户运营子域重新混层。

- 决策 2：`reconcile` 只保留摘要/引用。
  原因：完整 `reconcile` payload 仍带强研究派生属性，不应升格为事务域底层真相。

- 决策 3：compat 文件仅作迁移期影子写出。
  原因：移动端和历史工具链可能仍依赖旧路径，先保 compat 再退出更稳。

## Risks / Trade-offs

- [风险] 数据库对象与 compat 文件双写期间状态不一致
  → 缓解：要求正式读取面先切到数据库对象，compat 仅做回退。

- [风险] `reconcile_summary` 与完整 payload 的语义界限被重新打破
  → 缓解：spec 明确摘要只保留索引/引用，不承诺完整 payload 主真相。

- [风险] 账户运营对象拆分过细增加迁移成本
  → 缓解：保持对象数有限，不再继续细分新的事务域子对象。

## Migration Plan

1. 定义 `sim-account-db-persistence` 正式能力。
2. 修改 `sim-account-auto-sync`、`sim-account-holdings-sync`、`position-aware-reconcile-run` 和数据库治理 specs。
3. 在实现阶段先引入数据库对象写入，再把文件路径降级为 compat。
4. 数据库读取稳定后再执行文件兼容退出。

## Open Questions

- 数据库层最终采用单 schema 逻辑域还是独立库表分离，仍需实现阶段与事务域整体拆库设计对齐。
