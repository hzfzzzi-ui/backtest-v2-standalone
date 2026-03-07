## ADDED Requirements

### Requirement: 报告关键字段来源优先级合同
系统 MUST 为回测报告关键字段定义且执行统一来源优先级，确保同一 `exp_id` 在概览、报告与产物中的值一致可复核。

#### Scenario: 区间与基准字段按优先级解析
- **WHEN** 生成 `report.html`
- **THEN** 区间与基准 SHALL 优先取 `run_config.json.universe.start/end/benchmark`
- **THEN** 若 `run_config.json` 缺失，则 SHALL 回退到 `config.overrides.original_workbench_config.universe`
- **THEN** 若两者均缺失，则 SHALL 回退到 `run_meta.data`，并标记为 fallback

#### Scenario: Universe 数量按运行事实解析
- **WHEN** 生成“标的数量”字段
- **THEN** 系统 SHALL 优先使用 `run_meta.universe.raw_count`（resolver 实际数量）
- **THEN** 不得仅以配置层 `symbols.length` 作为 ALL_A/CSI* 模式下的最终展示值

### Requirement: 报告冲突可观测
系统 MUST 在报告或配套元数据中记录关键字段的数据来源与冲突处理结果，用于排查口径漂移。

#### Scenario: 存在多来源冲突
- **WHEN** 同一字段在多个来源中取值不一致
- **THEN** 系统 SHALL 按合同优先级选值
- **THEN** 系统 SHALL 记录选中来源、被覆盖来源与冲突策略（如 `config_id_overrides_workbench`）

### Requirement: 漏斗与绩效口径一致
系统 MUST 固定绩效与漏斗字段的数据源，避免混用造成解释偏差。

#### Scenario: 绩效口径
- **WHEN** 报告渲染 CAGR/Sharpe/MDD
- **THEN** 系统 SHALL 使用 `perf.json` 作为唯一数据源

#### Scenario: 漏斗口径
- **WHEN** 报告渲染 `raw_signal/blocked/orders/skipped/closed_trades`
- **THEN** 系统 SHALL 优先使用 `funnel.csv`
- **THEN** 仅在 `funnel.csv` 缺失时回退 `run_meta.counters`
