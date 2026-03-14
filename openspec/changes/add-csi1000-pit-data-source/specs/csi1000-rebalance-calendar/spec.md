## ADDED Requirements

### Requirement: 中证1000调样日历必须显式版本化
系统 MUST 为 `CSI1000` 维护一份显式版本化的调样生效日历，作为 PIT 快照抓取的唯一日历输入，而不是隐式使用“每月月末”或“固定间隔采样”近似。

#### Scenario: 使用版本化调样日历
- **WHEN** 系统为 `CSI1000` 生成 PIT 快照抓取计划
- **THEN** 系统 MUST 从显式日历文件读取 `effective_date`、`source` 和版本信息
- **THEN** 系统 MUST NOT 默认退回到“按月采样”作为正式研究口径

#### Scenario: 日历版本进入运行元信息
- **WHEN** 使用某一版 `CSI1000` 调样日历生成 PIT 数据
- **THEN** 导入链路和运行元信息 MUST 记录该日历版本、来源和生成时间
- **THEN** `run_meta.json` 或等价元信息 MUST 暴露 `rebalance_calendar_version`、`rebalance_calendar_source` 和 `rebalance_calendar_generated_at`

### Requirement: 中证1000调样日历必须覆盖定期调整与临时调整
系统 MUST 支持同时记录 `CSI1000` 的半年度定期调整生效日和临时调整生效日，并区分它们的事件类型，避免把临时调整丢失或错误并入定期调整。

#### Scenario: 记录半年度定期调整
- **WHEN** 维护 `CSI1000` 调样日历
- **THEN** 日历 MUST 至少能记录每年定期调整的生效日期和事件类型 `scheduled`

#### Scenario: 记录临时调整
- **WHEN** 存在中证官方公布的临时调整生效日
- **THEN** 日历 MUST 能显式记录该日期和事件类型 `ad_hoc`
- **THEN** 后续 PIT 快照抓取 MUST 将其视为独立事件处理

### Requirement: 日历缺口必须被审计
系统 MUST 在生成 `CSI1000` PIT 数据前审计调样日历的连续性和覆盖范围，避免因为缺失年份、缺失事件或日期乱序导致成分历史重建错误。

#### Scenario: 生效日乱序或重复
- **WHEN** 调样日历存在重复 `effective_date`、日期倒序或同日多条未解释事件
- **THEN** 系统 MUST 阻止继续生成正式 PIT 变更文件
- **THEN** 系统 MUST 报告具体冲突日期

#### Scenario: 覆盖范围不足
- **WHEN** 回测区间早于调样日历最早有效日期，或日历未覆盖请求区间内的应有调样事件
- **THEN** 系统 MUST 报告覆盖缺口
- **THEN** 系统 MUST 不得将生成结果标记为正式 PIT 数据
