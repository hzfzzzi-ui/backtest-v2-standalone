## Why

当前 `public` schema 是共享库，研究主线只依赖少数核心表，但这些表的结构治理还不够清晰：一部分 PIT 主表缺少与主查询模式匹配的索引，一部分历史备份表长期留在主 schema 中，`pit_trade_cal` 已落库却未进入运行时主路径。继续在这种状态下扩展，会增加查询退化、表角色混淆和后续变更难以分级审计的风险。

现在需要先做一次“只做最小改动、不碰研究口径”的数据库结构优化提案，把可以直接推进的 L2 项和必须先明确 spec 的 L3 项拆开，给后续实施提供可审计边界。

## What Changes

- 明确研究主线数据库核心表、辅助表、外围业务表、备份/临时表的分类口径，并固定为结构治理基线。
- 为核心研究表补充与当前主查询模式匹配的最小必要索引建议，优先覆盖 `pit_index_constituents` 和 `pit_industry_history`。
- 为持久化备份表给出治理规则，避免继续在 `public` schema 中累积一次性历史表。
- 给出一套 L2/L3 分级实施清单：
- L2：不改变查询语义、不改变研究口径的索引、注释、runbook、备份治理。
- L3：可能改变表约束、主键、运行时日历来源或写入合同的结构调整，仅形成 spec，不默认实施。
- 为每一类变更提供 DDL 草案、验证方法、风险提示和回退路径。

## Capabilities

### New Capabilities
- `research-db-structure-governance`: 定义研究主线 PostgreSQL 核心表的最小化结构治理、DDL 分级边界、验证与回退要求。

### Modified Capabilities

无。

## Impact

- 受影响系统：PostgreSQL `public` schema 中的研究主线表与少量外围表。
- 受影响表：`pams_ohlcv_daily`、`pit_index_daily`、`pit_index_constituents`、`pit_industry_history`、`pit_security_master`、`pit_st_history`、`pit_trade_cal`，以及 `pams_transactions*`、`pams_holdings_snapshot_backup_20260215` 等治理对象。
- 受影响代码路径：运行时数据访问、Universe 解析、市场快照、数据刷新脚本、运维 runbook。
- 不在本次变更内：baseline 主逻辑、信号时点、执行时点、组合构建逻辑、任何会改变研究口径的字段含义或查询语义。
