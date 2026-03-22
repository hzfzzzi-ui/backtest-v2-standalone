## ADDED Requirements

### Requirement: 历史指数成分数据必须在进入回测前通过质量分类
系统 MUST 在 `PIT_DYNAMIC` 指数股票池进入回测前，对成员历史数据做质量分类，至少区分 `pit_verified`、`approximate` 和 `static_fallback`，并将分类结果写入运行元信息。

#### Scenario: 识别正式 PIT 数据
- **WHEN** 指数成分历史包含多个生效日期、存在正常的移出记录，且覆盖回测区间内的调整事件
- **THEN** 系统 MUST 将该数据集标记为 `pit_verified`

#### Scenario: 识别静态 fallback
- **WHEN** 指数成分历史满足“`membership_history_rows == union_symbol_count`、`count(distinct start_date) == 1` 且 `end_date` 全为空”之类的静态快照特征
- **THEN** 系统 MUST 将该数据集标记为 `static_fallback`

### Requirement: 正式研究运行必须阻断静态 fallback 的 PIT_DYNAMIC 指数股票池
系统 MUST 阻断使用 `static_fallback` 质量等级的 `PIT_DYNAMIC` 指数股票池进入正式研究运行，防止静态快照伪装成 PIT 历史。

#### Scenario: 阻断中证1000静态 fallback
- **WHEN** `universe_mode='CSI1000'` 且 `membership_mode='PIT_DYNAMIC'`，并被审计为 `static_fallback`
- **THEN** 系统 MUST 拒绝将该数据集标记为 baseline 级正式研究输入
- **THEN** 系统 MUST 输出明确告警，说明阻断原因和审计指标

#### Scenario: 允许显式低保真研究
- **WHEN** 用户显式选择低保真研究模式或应急导入模式
- **THEN** 系统 MAY 允许继续运行
- **THEN** 系统 MUST 在 `run_meta.json` 和相关审计输出中把该运行标记为 `approximate` 或 `static_fallback`

### Requirement: Universe membership 审计结果必须可观测
系统 MUST 将成分历史审计结果暴露到回测元信息，便于前端、报告和研究脚本验证股票池质量，而不是只在日志中输出。

#### Scenario: 运行元信息包含审计摘要
- **WHEN** 回测使用带历史成分的指数股票池
- **THEN** `run_meta.json` MUST 包含 `membership_data_quality`、`membership_source`、`membership_history_rows`、`distinct_start_dates`、`open_rows` 和 `audit_status`

#### Scenario: 审计失败可被报告引用
- **WHEN** 审计识别出静态 fallback、覆盖缺口或异常日期
- **THEN** 审计输出 MUST 能为 `audit.json` 或研究报告提供结构化证据引用，而不是仅保留自由文本日志
- **THEN** 该结构化证据 MUST 至少包含 `audit_reason`、`membership_data_quality`、`membership_source`、`distinct_start_dates`、`open_rows` 和 coverage 相关指标
