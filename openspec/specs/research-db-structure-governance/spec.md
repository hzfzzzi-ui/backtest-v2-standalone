# research-db-structure-governance Specification

## Purpose
TBD - created by archiving change optimize-core-db-structure. Update Purpose after archive.
## Requirements
### Requirement: 核心研究表结构治理分层
系统 MUST 对共享 PostgreSQL `public` schema 中的数据库对象进行分层治理，并将研究主线数据库优化限制在明确定义的核心研究表范围内。

#### Scenario: 识别核心研究表
- **WHEN** 团队制定或评审回测系统数据库结构优化方案
- **THEN** 方案 MUST 将 `pams_ohlcv_daily`、`pit_index_daily`、`pit_index_constituents`、`pit_industry_history`、`pit_security_master`、`pit_st_history` 识别为核心研究表
- **THEN** 不属于上述集合的共享业务表 MUST NOT 因“顺手优化”被纳入同一轮核心研究改动

#### Scenario: 识别备份与临时对象
- **WHEN** 团队盘点 `public` schema 中的备份表或临时脚本对象
- **THEN** `*_backup_*` 持久表 MUST 被视为治理债务而非核心研究表
- **THEN** 会话级 `tmp_*` 表 MUST 被视为脚本临时对象，不得被误判为长期结构资产

### Requirement: L2 数据库优化只允许非语义型 DDL
系统 SHALL 将 L2 数据库结构优化限定为不会改变研究口径、查询结果集和运行时合同的非语义型 DDL。

#### Scenario: 对 PIT 成分表执行 L2 优化
- **WHEN** 团队对 `pit_index_constituents` 制定首批 L2 优化
- **THEN** 允许的 DDL MUST 限定为新增非唯一索引、注释或 runbook 配套对象
- **THEN** 该优化 MUST NOT 改变表字段含义、查询条件语义或 Universe 结果集合

#### Scenario: 对 PIT 行业历史表执行 L2 优化
- **WHEN** 团队对 `pit_industry_history` 制定首批 L2 优化
- **THEN** 优化 MUST 优先覆盖 `industry_l1 + 生效区间 + ts_code` 查询模式
- **THEN** 该优化 MUST NOT 修改 `start_date` / `end_date` 的 PIT 解释方式

### Requirement: L2 DDL 必须内建验证与回退
每一个 L2 数据库结构变更 MUST 同时提供执行前基线、执行后验证和非破坏性回退方案。

#### Scenario: 执行索引变更前
- **WHEN** 团队准备执行任何 L2 索引 DDL
- **THEN** 方案 MUST 记录对应主查询的 `EXPLAIN` 基线
- **THEN** 方案 MUST 记录目标表的关键行数或去重统计，作为语义校验依据

#### Scenario: 执行索引变更后
- **WHEN** 团队完成任何 L2 索引 DDL
- **THEN** 方案 MUST 重新执行相同查询的 `EXPLAIN` 或 `EXPLAIN ANALYZE`
- **THEN** 方案 MUST 验证关键结果集与变更前一致
- **THEN** 方案 MUST 提供 `DROP INDEX CONCURRENTLY` 级别的回退 DDL

### Requirement: 约束增强与运行时数据源切换属于 L3
任何可能改变写入合同、运行时数据来源、共享库兼容性或 PIT 语义边界的结构调整 MUST 作为 L3 变更单独立项。

#### Scenario: 提议增加约束
- **WHEN** 团队提议为 `pit_index_constituents`、`pit_industry_history` 或 `pit_st_history` 增加主键、唯一约束、非空约束或区间重叠约束
- **THEN** 该提议 MUST 被归类为 L3
- **THEN** 在独立 spec、数据审计和回归验证完成前 SHALL NOT 直接实施

#### Scenario: 提议切换交易日日历真源
- **WHEN** 团队提议将运行时交易日日历主来源从现有价格表切换到 `pit_trade_cal`
- **THEN** 该提议 MUST 被归类为 L3
- **THEN** 在明确验证口径一致性之前 SHALL NOT 与索引优化一并实施

### Requirement: 持久化备份表必须受治理约束
系统 MUST 对 `public` schema 中的持久化备份表建立治理边界，避免一次性脚本产物长期混入主结构认知。

#### Scenario: 新增持久化备份表
- **WHEN** 团队需要为运营或修复目的新增持久化备份表
- **THEN** 该表 MUST 记录来源、创建日期、预期保留期和删除/迁移责任人
- **THEN** 该表 MUST NOT 被标记为核心研究表

#### Scenario: 盘点既有备份表
- **WHEN** 团队盘点 `public` schema 中既有 `*_backup_*` 表
- **THEN** 盘点结果 MUST 明确这些表不属于 baseline 主线运行时依赖
- **THEN** 后续如需迁移或删除，必须通过独立变更执行

