## Context

当前仓库的市场数据消费链存在四类并行旧壳：

1. runtime compile 仍携带 `data_role / stocks_table / stocks_mapping_table`
2. `PostgresDataProvider` 仍按表名切换直接查表
3. `universe resolver` 自行直查 `pit_index_constituents / pit_industry_history / pit_security_master`
4. `market_snapshot_service` 仍保留历史直接查询路径

这些入口共同造成两个问题：

- 正式文档已经把市场数据主路径收敛到 `canonical_market` 与统一访问合同，但实现层仍在传播旧默认值
- 后续前端、事务域、执行层收敛都会继续被旧市场数据入口反向污染

这轮 change 的定位是 L2 架构收口改造：先在市场数据域建立正式消费边界，不改研究逻辑，不改 baseline 主口径，不同步推进事务域和前端实现。

## Goals / Non-Goals

**Goals:**

- 建立统一 `market data access contract` 作为正式市场数据消费边界
- 将 runtime compile 的正式市场数据入口固定为 `canonical_market`
- 让 `universe resolver` 与 `market snapshot` 的正式要求对齐统一访问层
- 把 V2 compat 的定位收回到迁移期兼容壳
- 为后续实现阶段提供清晰、可回归、可回退的任务拆分

**Non-Goals:**

- 不在本轮引入事务域数据库重构
- 不在本轮改前端实现
- 不在本轮改 baseline_V10.1 研究逻辑、执行时点或风控语义
- 不在本轮把 `outputs/` 全量迁入数据库
- 不在本轮引入 L2 市场数据实现

## Decisions

### 1. 新增统一 `market-data-access-contract`，而不是继续扩张 `pg_provider`

决定：

- 以新 capability 明确定义统一访问合同
- 该合同只按业务能力暴露，不按底表暴露

原因：

- 继续在 `pg_provider` 上叠加分支，只会把表切换开关继续固化成长期合同
- 新 capability 更适合约束 `price / benchmark / calendar / PIT / security master` 的统一输入与审计回显

备选：

- 继续用 `pg_provider` 作为正式访问边界  
  不采用：它天然与底表名、`data_role`、旧 runtime 默认值耦合

### 2. 第一批实现只覆盖 `L1 canonical`，不提前引入 `L2`

决定：

- 本 change 只定义并落第一批 `L1 canonical` 访问合同
- 文档里保留跨市场骨架，但不引入 `L2` 正式实现任务

原因：

- 当前无 `L2` 正式数据
- 先收 `L1 canonical` 可以最小化对 `baseline_V10.1` 的口径风险

备选：

- 同时把 `L2` 合同一起实现  
  不采用：无数据支撑，且会分散第一批重构目标

### 3. compat 层保留为迁移壳，但不再允许作为长期正式默认入口

决定：

- compat 仍允许服务旧 baseline 迁移和 shadow 对照
- 新的正式默认入口统一指向 `canonical_market`

原因：

- 直接硬删 compat 会放大迁移风险
- 继续把 compat 写成正式默认入口，则文档和实现会持续分叉

备选：

- 立即移除 compat 层  
  不采用：迁移风险高，且不符合“先收边界、后清旧壳”的顺序

### 4. 第一批消费者只迁三类：compile、resolver、snapshot

决定：

- 本 change 的实现任务只优先覆盖：
  - runtime compile
  - `universe resolver`
  - `market_snapshot_service`

原因：

- 这三类入口最典型，且跨模块影响大
- 它们都不需要先动事务域与前端壳

备选：

- 一次性迁全仓库所有直接 SQL  
  不采用：范围过大，无法保证最小改动和回归可控

## Risks / Trade-offs

- [Risk] 统一访问层落地后，旧配置可能仍隐含依赖 `data_role` 或表名切换  
  → Mitigation：在 compile 层保留迁移期 shadow source reference，并对 `baseline_V10.1` 做 compile 等价回归

- [Risk] `universe resolver` 迁移时可能引入 PIT 口径偏移  
  → Mitigation：先只改访问边界，不改现有 universe 规则，并保留基于 `as_of_date` 的回归对照

- [Risk] market snapshot 迁移后，某些历史直接 SQL 的字段映射会丢失  
  → Mitigation：要求统一访问层返回固定审计回显，并对 snapshot 输出结构做金样回归

- [Risk] compat 层降级会影响部分旧实验或旧脚本  
  → Mitigation：文档与 spec 中保留 compat 为迁移壳，并把“旧 baseline 迁移专用”写死

## Migration Plan

1. 先在 OpenSpec 中定义统一访问合同与相关 spec 修改
2. 第一批实现建立统一访问层骨架和 `L1 canonical` 能力面
3. 将 compile、resolver、snapshot 接入统一访问层
4. 保留 compat 迁移壳，但收掉默认正式入口语义
5. 用 `baseline_V10.1` 做 compile、resolver、snapshot 三组回归
6. 通过后，再进入下一轮“扫实现层旧入口并继续替换”

回退策略：

- 若统一访问层接入出现口径偏移，可回退到本 change 前的旧入口实现
- compile 层保留 shadow source reference，不在本轮直接删除 compat 代码路径

## Open Questions

- benchmark 标识在统一访问层里是否需要单独稳定 `benchmark_id` 字段，而不是仅复用 `symbol`
- 证券主数据能力是否需要在第一批就统一 code normalize / lineage resolve 的输出结构
- 第一批实现是否需要同步抽出统一 query audit helper，还是先在访问层内部局部实现
