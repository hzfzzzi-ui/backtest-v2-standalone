## ADDED Requirements

### Requirement: CSI1000 必须持久化 refresh 级成员快照侧表
系统 MUST 为 `CSI1000` 建立 refresh 级侧表，按每个 `refresh_date` 保存当日 constituent snapshot 中的全部 symbol，并保留该 refresh 对应的 `source`、`event_type`、`snapshot_trade_date` 与日历 lineage 元信息。系统 SHALL NOT 只保留区间变化结果而丢弃 refresh 级证据。

#### Scenario: 定期 refresh 写入侧表
- **WHEN** `CSI1000` 的某个 scheduled refresh 完成快照抓取并导入
- **THEN** 系统 MUST 为该 `refresh_date` 写入完整的 constituent snapshot 侧表记录
- **THEN** 每行 MUST 至少包含 `index_code`、`refresh_date`、`symbol`、`source`、`event_type` 和 `snapshot_trade_date`

#### Scenario: 零差异 refresh 仍然落证
- **WHEN** 某个 refresh 事件与上一次快照相比没有任何 constituent diff
- **THEN** 主区间表 MAY 不新增或关闭任何行
- **THEN** 系统 MUST 仍然把该 `refresh_date` 的 snapshot 写入 refresh 侧表

### Requirement: refresh 侧表必须显式映射到主 PIT 区间真值
系统 MUST 让 refresh 侧表中的每个 snapshot row 显式映射到 `pit_index_constituents` 中的主 PIT 区间行，而不是独立保存另一套区间真值。该映射 MUST 至少暴露 `constituent_start_date` 作为自然键的一部分。

#### Scenario: snapshot row 映射到主表区间
- **WHEN** 导入某个 `refresh_date` 的 constituent snapshot
- **THEN** 系统 MUST 为每个 symbol 找到覆盖该 `refresh_date` 的主表区间行
- **THEN** 侧表 MUST 记录可回溯到该区间行的自然键字段

#### Scenario: 找不到主表区间时导入失败
- **WHEN** refresh snapshot 中某个 symbol 无法映射到任何覆盖该 `refresh_date` 的主 PIT 区间行
- **THEN** 系统 MUST 阻止该批 refresh sidecar 被标记为导入成功
- **THEN** 系统 MUST 输出结构化错误，指出冲突的 `refresh_date` 和 `symbol`

### Requirement: refresh 侧表必须记录 scheduled 与 ad_hoc/non-PIT refresh 事件
系统 MUST 允许 refresh 侧表同时记录 scheduled 与 ad_hoc/non-PIT refresh 事件，而 SHALL NOT 因为该事件没有触发 constituent diff 就直接丢弃。

#### Scenario: 记录 ad_hoc/non-PIT refresh
- **WHEN** 调样日历或人工 manifest 声明某个 `event_type='ad_hoc'` 的 refresh 事件
- **THEN** 系统 MUST 在 refresh 侧表中保留该事件对应的 constituent snapshot
- **THEN** 该事件 MUST 继续暴露 `event_type='ad_hoc'` 或等价显式标签
