## ADDED Requirements

### Requirement: CSI1000 成员历史审计必须显式消费 refresh 侧表证据
系统 MUST 在审计 `CSI1000` `PIT_DYNAMIC` 成员历史时同时读取 refresh 侧表证据，用于区分“真实发生过 refresh 但无成分变化”和“根本没有 refresh 证据”两类情况。

#### Scenario: 零差异 refresh 被审计识别
- **WHEN** 某个 refresh 事件在主区间表中没有新增 `start_date`，但 refresh 侧表中存在完整 snapshot
- **THEN** 审计 MUST 将其识别为“零差异 refresh 已有证据”
- **THEN** 审计 SHALL NOT 因为 `distinct_start_dates` 未增加就把该事件当作缺失 refresh

### Requirement: CSI1000 审计必须显式暴露 Tushare 覆盖下限
系统 MUST 在 `CSI1000` 审计输出中显式暴露 `Tushare` provider floor 和未覆盖窗口。若 `required_start` 早于该 floor，审计 MUST 将该历史链维持为 uncovered/approximate，而不是 `pit_verified`。

#### Scenario: required_start 早于 provider floor
- **WHEN** `required_start` 早于 `Tushare` 最早可用的 `CSI1000` refresh 快照日期
- **THEN** 审计输出 MUST 暴露 `provider_floor_date`
- **THEN** `membership_data_quality` MUST 不是 `pit_verified`

#### Scenario: covered window 内的 refresh 证据完整
- **WHEN** `required_start` 晚于等于 provider floor，且主区间表与 refresh 侧表覆盖全部 refresh 事件
- **THEN** 审计 MAY 继续将该 covered window 评为 `pit_verified`
- **THEN** 审计输出 MUST 同时暴露 `refresh_event_count` 或等价 refresh 统计
