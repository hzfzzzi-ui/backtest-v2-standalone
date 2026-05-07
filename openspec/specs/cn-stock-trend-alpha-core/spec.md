# cn-stock-trend-alpha-core Specification

## Purpose
定义当前正式 A 股股票 alpha 主干 `baseline_V10.1` 在 governed multi-sleeve 主线中的正式角色与边界。
## Requirements
### Requirement: baseline_V10.1 必须被正式重定位为股票alpha sleeve
系统 MUST 将当前正式主线 `baseline_V10.1` 的系统语义重定位为 `cn_stock_trend_alpha_core`。该能力 SHALL 表达 A 股子系统中的股票 alpha sleeve，而 SHALL NOT 再被描述为整个 A 股系统本身。

#### Scenario: 研究配置与产物描述股票alpha sleeve
- **WHEN** 系统运行 `baseline_V10.1` 或其正式继承研究
- **THEN** 运行描述 MUST 将其标识为 `cn_stock_trend_alpha_core`
- **THEN** 产物 SHALL NOT 再把该策略单独表述为整个 A 股系统

### Requirement: 股票alpha sleeve 必须消费 Governor 预算而不是定义全组合总仓位
`cn_stock_trend_alpha_core` MUST 在 Governor 下发的 `sleeve_budget` 内运行其 breakout、residual ranking、candidate quality 与本地 exits 逻辑。该 sleeve MAY 继续拥有股票层内部约束，但 SHALL NOT 定义全组合总风险预算。

#### Scenario: 股票alpha sleeve 在预算内运行
- **WHEN** 股票 alpha sleeve 进入建仓与调仓阶段
- **THEN** 该 sleeve MUST 消费 Governor 下发的预算上限
- **THEN** 该 sleeve MAY 继续应用 `max_positions`、`single_stock_cap`、`industry_cap` 等本地约束

#### Scenario: 股票alpha sleeve 不得覆盖总预算
- **WHEN** 股票 alpha sleeve 的本地 sizing 结果与 Governor 总预算冲突
- **THEN** Governor 预算 MUST 具有更高优先级
- **THEN** 股票 alpha sleeve SHALL NOT 把本地 sizing 结果提升为新的全组合真相

### Requirement: 股票alpha sleeve 必须保留股票alpha主干边界
`cn_stock_trend_alpha_core` MUST 保留“右侧趋势突破 + 动量残差排序”的主干边界，并将左侧蓝筹逻辑视为未来预留能力。Phase 1 SHALL NOT 将左侧蓝筹、ETF beta 或保险层逻辑直接并入该 sleeve。

#### Scenario: Phase 1 不混入左侧蓝筹或ETF逻辑
- **WHEN** 系统定义 `cn_stock_trend_alpha_core` 的 Phase 1 正式范围
- **THEN** 该范围 MUST 只覆盖股票 alpha 主干
- **THEN** `value_bluechip_satellite`、`cn_etf_beta` 和 `insurance_overlay` SHALL 保持在该 sleeve 之外

### Requirement: 个股子系统必须在进入执行内核前完成候选兼容裁决
`cn_stock_trend_alpha_core` 在多信号组合路径下 MUST 将同股兼容裁决、市场状态权重覆写、子系统名额分配和最终候选截断视为子系统上游候选边界的一部分。该边界结果 MUST 在进入执行内核前固定下来，执行内核 SHALL NOT 再重建这些裁决。

#### Scenario: 多信号个股路径进入执行内核
- **WHEN** 个股多信号路径已经形成当日组合后候选
- **THEN** 系统 MUST 在进入执行内核前完成子系统名额和兼容裁决
- **THEN** 执行内核 SHALL 只接收裁决后的最终候选集合

### Requirement: 个股子系统必须在进入执行内核前形成候选规划真相
`cn_stock_trend_alpha_core` MUST 在进入执行内核前形成自己的候选规划真相，包括现金感知候选选择、轮换替换和候选排序后的最终保留集合。该子系统 SHALL NOT 把这些候选规划兼容语义留给共享执行内核临时决定。

#### Scenario: 现金感知候选选择启用
- **WHEN** 个股子系统启用现金感知候选选择
- **THEN** 子系统 MUST 在进入执行内核前完成最终候选集合决策
- **THEN** 执行内核 SHALL 只接收规划结果

#### Scenario: 轮换替换启用
- **WHEN** 个股子系统启用轮换替换
- **THEN** 子系统 MUST 在候选规划阶段形成替换对与保留候选结果
- **THEN** 执行内核 SHALL NOT 再自行决定是否执行候选替换
