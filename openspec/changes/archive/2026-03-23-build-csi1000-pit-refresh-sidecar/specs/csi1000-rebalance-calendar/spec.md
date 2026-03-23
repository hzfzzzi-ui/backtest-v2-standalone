## ADDED Requirements

### Requirement: 中证1000调样日历必须保留零差异 refresh 事件
系统 MUST 允许 `CSI1000` 调样日历显式保留“有 refresh 证据但与上一快照无 constituent diff”的事件，避免这些日期在后续导入中被当作无效事件直接删除。

#### Scenario: 定期 refresh 无成分变化
- **WHEN** 某个日历事件存在正式 refresh 证据，但与上一快照相比成分完全相同
- **THEN** 该事件 MUST 继续留在调样日历中
- **THEN** 后续 refresh sidecar MUST 仍然为该日期保留 snapshot 记录

#### Scenario: 临时 non-PIT refresh 无成分变化
- **WHEN** 某个 `event_type='ad_hoc'` 的 refresh 事件没有触发 constituent diff
- **THEN** 日历 MUST 继续保留该事件
- **THEN** 导入链路 SHALL NOT 因为“零变化”而删除该日期
