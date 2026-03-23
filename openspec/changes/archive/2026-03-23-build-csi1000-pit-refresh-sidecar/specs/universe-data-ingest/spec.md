## ADDED Requirements

### Requirement: CSI1000 导入链必须同时重建区间主表与 refresh 侧表
系统 MUST 在 `CSI1000` PIT 导入时同时重建 `pit_index_constituents(index_code='000852.SH')` 与 refresh 侧表，而 SHALL NOT 只导入 `changes.csv` 后丢弃 refresh 级 snapshots。

#### Scenario: Tushare refresh 导入
- **WHEN** 执行 `CSI1000` 的 Tushare PIT refresh 导入
- **THEN** 系统 MUST 同时消费 `changes.csv` 与 `snapshots.csv`
- **THEN** 导入事务 MUST 同时替换主区间表与 refresh 侧表的 `000852.SH` 分区

#### Scenario: 手工 official manifest 导入
- **WHEN** 执行 `CSI1000` 的 manual manifest 导入
- **THEN** 系统 MUST 同时生成并导入主区间 changes 与 refresh snapshots
- **THEN** refresh 侧表 MUST 保留 `source_url` 或等价 lineage 元信息

### Requirement: CSI1000 Tushare 导入必须显式记录实际快照交易日
系统 MUST 把 `Tushare index_weight` 实际命中的 `trade_date` 作为结构化字段保存到 `CSI1000` snapshots 和 refresh 侧表，而 SHALL NOT 继续仅把该值拼接进 `source_note`。

#### Scenario: Tushare 快照命中晚于 effective_date 的交易日
- **WHEN** 系统用 `lookahead` 在 `effective_date` 之后命中第一天可用的 `trade_date`
- **THEN** snapshots 输出 MUST 显式记录该 `snapshot_trade_date`
- **THEN** refresh 侧表 MUST 保留同一字段，供后续 SQL 与审计查询

### Requirement: CSI1000 Tushare 导入必须显式暴露覆盖下限
系统 MUST 在 `CSI1000` Tushare 导入摘要中显式暴露 provider 的最早快照覆盖日，并对早于该日期的目标窗口给出 uncovered 结论，而 SHALL NOT 把缺口伪装成 formal PIT 历史。

#### Scenario: 请求窗口早于 Tushare 最早覆盖日
- **WHEN** 用户目标窗口早于当前 `Tushare index_weight(000852.SH)` 的最早可用快照日期
- **THEN** 导入摘要 MUST 显式输出 `provider_floor_date` 或等价字段
- **THEN** 系统 MUST 将该窗口标记为 uncovered/approximate，而不是 formal

#### Scenario: 2012-2015 无源窗口不得被伪补齐
- **WHEN** `Tushare` 对 `2012-01-01 ~ 2015-07-30` 无可用 `CSI1000` 快照
- **THEN** 系统 MUST 保持该区间为无覆盖真相
- **THEN** 系统 SHALL NOT 用首个可用快照前向填充或静态 fallback 伪造正式 PIT
