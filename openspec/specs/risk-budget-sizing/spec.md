# risk-budget-sizing Specification

## Purpose
系统化风险预算仓位管理，从组合总风险到单笔仓位再到 sleeve 预算做自上而下分配，并保留 drawdown ladder、渐进式回撤保护与 Governor 统一预算收口能力。

## Requirements

### Requirement: 组合风险预算计算
系统 SHALL 在每个交易日计算组合风险预算，作为所有新开仓的风险上限。

#### Scenario: 正常市场（无回撤）
- **WHEN** 当前回撤 < 10%
- **THEN** `portfolio_risk` SHALL 等于 `base_portfolio_risk × trend_multiplier`
- **THEN** 默认值 SHALL 为 `0.06 × 1.0 = 6%`

#### Scenario: 趋势倍数预留
- **WHEN** `trend_multiplier` 配置为非 1.0 值
- **THEN** 系统 SHALL 将 `base_portfolio_risk` 乘以 `trend_multiplier`
- **THEN** 本次版本默认 `trend_multiplier = 1.0`

### Requirement: 渐进式回撤缩放
系统 SHALL 根据当前回撤幅度渐进降低组合风险，替代二元熔断机制。

#### Scenario: 回撤 10%-15%
- **WHEN** 当前回撤 ≥ 10% 且 < 15%
- **THEN** `portfolio_risk` SHALL 等于 `base × trend × dd_scale_10`
- **THEN** 默认 `dd_scale_10 = 0.8`

#### Scenario: 回撤 15%-20%
- **WHEN** 当前回撤 ≥ 15% 且 < 20%
- **THEN** `portfolio_risk` SHALL 等于 `base × trend × dd_scale_15`
- **THEN** 默认 `dd_scale_15 = 0.6`

#### Scenario: 回撤 20%-25%
- **WHEN** 当前回撤 ≥ 20% 且 < 25%
- **THEN** `portfolio_risk` SHALL 固定为 `dd_fixed_20`
- **THEN** 默认 `dd_fixed_20 = 0.03`（3%）
- **THEN** 此值不受 `trend_multiplier` 影响

#### Scenario: 回撤红线（≥25%）
- **WHEN** 当前回撤 ≥ `dd_stop_pct`（默认 25%）
- **THEN** 系统 SHALL 拒绝所有新买入信号
- **THEN** 已持仓的退出规则 SHALL 继续正常执行
- **THEN** `dd_stop_block_count` 计数器 SHALL 累加被拦截的买入信号数

### Requirement: 单笔风险分配
系统 SHALL 将组合风险均匀分配到各仓位。

#### Scenario: 单笔风险计算
- **WHEN** 组合风险预算已计算
- **THEN** 风险分母 SHALL 为 `max(当前持仓数, max_positions × min_active_ratio)`
- **THEN** 默认 `min_active_ratio = 0.6`
- **THEN** `per_trade_risk = portfolio_risk / 分母`
- **THEN** `risk_amount = nav × per_trade_risk`

#### Scenario: 分母下限保护
- **WHEN** 当前持仓为 0 且 `max_positions = 10`、`min_active_ratio = 0.6`
- **THEN** 风险分母 SHALL 为 6（而非 0）
- **THEN** 防止空仓时单笔风险过大

### Requirement: ATR 定仓公式
系统 SHALL 基于 ATR 止损距离反算仓位股数。

#### Scenario: 正常 ATR 定仓
- **WHEN** 买入信号触发且 ATR 值可用（> 0）
- **THEN** 止损距离 SHALL 为 `atr_stop_k × ATR`
- **THEN** 股数 SHALL 为 `risk_amount / 止损距离`
- **THEN** 股数 SHALL 按 `lot_size` 向下取整
- **THEN** 默认 `atr_stop_k = 2.0`

#### Scenario: ATR 不可用降级
- **WHEN** 某标的 ATR 值为 NaN 或 0
- **THEN** 系统 SHALL 降级使用等权仓位（`nav / max_positions / price`）
- **THEN** 不跳过买入

#### Scenario: 单票上限安全阀
- **WHEN** ATR 定仓计算的仓位金额超过 `nav × single_stock_cap`
- **THEN** 股数 SHALL 被截断至 `nav × single_stock_cap / price`
- **THEN** 截断后仍按 `lot_size` 向下取整

### Requirement: ATR 止损倍数统一
仓位计算和退出规则 ATR 止损 SHALL 共用同一个 `atr_stop_k` 配置值。

#### Scenario: 仓位与止损一致
- **WHEN** `atr_stop_k = 2.0`
- **THEN** 仓位公式使用 `2.0 × ATR` 作为止损距离
- **THEN** ATR 止损退出规则使用同一个 `2.0` 作为 k 值
- **THEN** 不存在独立的退出 ATR k 值配置

### Requirement: 风险预算默认关闭
系统 SHALL 默认关闭风险预算，保持向后兼容。

#### Scenario: 关闭时走等权逻辑
- **WHEN** `risk_budget.enabled = false`
- **THEN** 仓位计算 SHALL 使用等权逻辑（`nav / max_positions`）
- **THEN** 回撤缩放 SHALL 不生效
- **THEN** 行为与本次改动前完全一致

#### Scenario: 旧配置静默忽略
- **WHEN** JSON 配置包含旧字段 `enable_volatility_sizing` 或 `enable_drawdown_breaker`
- **THEN** config loader SHALL 静默忽略这些字段（不报错）

### Requirement: 风险预算可观测性
系统 SHALL 输出风险预算相关的每日状态和汇总计数器。

#### Scenario: 每日 row 字段
- **WHEN** 回测运行且 risk budget 启用
- **THEN** 每日 daily_row SHALL 包含 `portfolio_risk`（组合风险）
- **THEN** SHALL 包含 `per_trade_risk`（单笔风险）
- **THEN** SHALL 包含 `dd_scale`（回撤缩放系数）
- **THEN** SHALL 包含 `trend_mult`（趋势倍数）

#### Scenario: 汇总计数器
- **WHEN** 回测完成
- **THEN** counters SHALL 包含 `dd_scale_08_count`（0.8x 缩放天数）
- **THEN** SHALL 包含 `dd_scale_06_count`（0.6x 缩放天数）
- **THEN** SHALL 包含 `dd_fixed_03_count`（固定 3% 天数）
- **THEN** SHALL 包含 `dd_stop_count`（停止交易天数）
- **THEN** SHALL 包含 `dd_stop_block_count`（被拦截的买入信号总数）

### Requirement: 前端风险预算配置
前端 SHALL 在"仓位风控"区块提供风险预算的配置 UI。

#### Scenario: 风险预算 UI 控件
- **WHEN** 用户查看"仓位风控"配置区域
- **THEN** SHALL 显示"风险预算"总开关 checkbox（默认关闭）
- **THEN** 开启后 SHALL 显示：基础组合风险 %（默认 6）、ATR 止损倍数（默认 2.0）、最小活跃比例（默认 0.6）
- **THEN** SHALL 显示回撤缩放参数：10%/15%/20% 阈值对应的缩放系数、25% 红线

#### Scenario: 移除旧控件
- **WHEN** 页面渲染
- **THEN** SHALL 不存在"波动率调仓"checkbox 及参数
- **THEN** SHALL 不存在"回撤熔断"checkbox 及参数

### Requirement: Risk budget sizing 支持 legacy overlay 归零

系统 SHALL 允许 `risk-budget-sizing` 在 `ma200_legacy` 模式下消费一个辅助 veto overlay。

#### Scenario: TURN_WEAK overlay 命中时预算归零

- **WHEN** `regime_engine.engine = ma200_legacy`
- **AND** `legacy_turn_weak_overlay.enabled = true`
- **AND** 辅助 weekly 状态为 `TURN_WEAK`
- **THEN** `risk_budget_multiplier` MUST 为 `0.00`

#### Scenario: 非 TURN_WEAK 日保持 legacy 原预算

- **WHEN** `regime_engine.engine = ma200_legacy`
- **AND** `legacy_turn_weak_overlay.enabled = true`
- **AND** 辅助 weekly 状态不为 `TURN_WEAK`
- **THEN** 系统 MUST 保持 legacy 原有预算映射

### Requirement: Risk budget sizing 支持状态预算乘子

系统 SHALL 允许 `risk-budget-sizing` 消费 `regime engine` 输出的 `risk_budget_multiplier`。

当 `regime_engine.engine = weekly_five_state` 时，系统 MUST 支持以下预算模式：

- `five_state`
- `three_state`
- `asymmetric_budget`

系统 SHALL 允许 `risk-budget-sizing` 消费由 regime engine 输出的 `risk_budget_multiplier`。

当 `regime_engine.engine = weekly_five_state` 时：

- `BULL_MAIN` -> `1.00`
- `TURN_STRONG` -> `0.70`
- `LIGHT_TREND` -> `0.40`
- `TURN_WEAK` -> 默认 `0.15`
- `DEFENSIVE` -> `0.00`

系统 SHALL 允许 `risk-budget-sizing` 消费 `regime engine` 输出的 `risk_budget_multiplier`。

当 `regime_engine.engine = weekly_five_state` 时，系统 MUST 支持两种预算模式：

- `five_state`
- `three_state`

#### Scenario: weekly_five_state 非对称预算模式

- **WHEN** `regime_engine.engine = weekly_five_state` 且 `risk_budget_mode = asymmetric_budget`
- **THEN** 系统 SHALL 使用非对称预算映射：
  - `BULL_MAIN -> 1.00`
  - `TURN_STRONG -> 0.70`
  - `LIGHT_TREND -> 0.40`
  - `TURN_WEAK -> 0.00`
  - `DEFENSIVE -> 0.00`

#### Scenario: TURN_WEAK 在非对称模式下关闭预算

- **WHEN** `risk_budget_mode = asymmetric_budget` 且 `market_state_5 = TURN_WEAK`
- **THEN** `risk_budget_multiplier` MUST 为 `0.00`

#### Scenario: TURN_STRONG 在非对称模式下不升到满仓

- **WHEN** `risk_budget_mode = asymmetric_budget` 且 `market_state_5 = TURN_STRONG`
- **THEN** `risk_budget_multiplier` MUST 保持 `0.70`
- **THEN** 系统 MUST 不得将其抬升为 `1.00`

#### Scenario: 风险预算随状态缩放
- **WHEN** weekly five-state 运行
- **THEN** 组合风险预算 SHALL 乘以状态预算乘子

#### Scenario: weekly_five_state 五档预算模式

- **WHEN** `regime_engine.engine = weekly_five_state` 且 `risk_budget_mode = five_state`
- **THEN** 系统 SHALL 使用原五档预算映射：
  - `BULL_MAIN -> 1.00`
  - `TURN_STRONG -> 0.70`
  - `LIGHT_TREND -> 0.40`
  - `TURN_WEAK -> 0.15`
  - `DEFENSIVE -> 0.00`

#### Scenario: weekly_five_state 三档预算模式

- **WHEN** `regime_engine.engine = weekly_five_state` 且 `risk_budget_mode = three_state`
- **THEN** 系统 SHALL 将五档原始状态折叠为三档预算 bucket：
  - `BULL_MAIN / TURN_STRONG -> RISK_ON -> 1.00`
  - `LIGHT_TREND -> NEUTRAL -> 0.40`
  - `TURN_WEAK / DEFENSIVE -> RISK_OFF -> 0.00`

#### Scenario: 三档预算模式不保留 TURN_WEAK 低仓预算

- **WHEN** `risk_budget_mode = three_state`
- **THEN** `TURN_WEAK` MUST 不再映射到 `0.15`
- **THEN** `TURN_WEAK` MUST 归入 `RISK_OFF`

#### Scenario: 默认仍为五档预算模式

- **WHEN** 用户未显式设置 `risk_budget_mode`
- **THEN** 系统 SHALL 默认使用 `five_state`### Requirement: TURN_WEAK 预算保持低自由度
系统 SHALL 仅允许 `TURN_WEAK` 风险预算在 `0.10~0.20` 范围内微调，默认值为 `0.15`。

#### Scenario: TURN_WEAK 默认预算
- **WHEN** 用户未显式配置
- **THEN** `TURN_WEAK` 风险预算 SHALL 默认为 `0.15`

### Requirement: DEFENSIVE 预算为零
当 `market_state_5 = DEFENSIVE` 时，系统 MUST 将状态预算乘子设为 `0.00`，从而禁止新开仓。

#### Scenario: 防守状态零预算
- **WHEN** `market_state_5 = DEFENSIVE`
- **THEN** `risk_budget_multiplier = 0.00`

### Requirement: Risk budget sizing 必须为Governor输出总预算与sleeve预算
当 A 股子系统启用统一总控时，`risk-budget-sizing` MUST 支持输出可供 Governor 消费和下发的两级预算：
- `total_risk_budget`
- `sleeve_budgets`

系统 MUST 允许在保持既有风险预算公式的同时，将其从“单策略预算”扩展为“全组合总预算 + sleeve 预算”的正式 contract。

#### Scenario: 风险预算输出总预算与sleeve预算
- **WHEN** Governor 模式启用且系统完成当日预算计算
- **THEN** 预算输出 MUST 同时包含全组合总预算和至少一个 sleeve 预算映射

### Requirement: Risk budget sizing 必须明确总预算优先于本地sizing
`risk-budget-sizing` MUST 明确总预算优先级高于任意 sleeve 本地 sizing 结果。股票 sleeve 与 ETF sleeve MAY 在既有公式内继续执行本地 sizing，但 SHALL NOT 覆盖 Governor 下发的全组合预算上限。

#### Scenario: 本地 sizing 与总预算冲突
- **WHEN** 某一 sleeve 的本地 sizing 结果超过 Governor 允许的预算
- **THEN** 系统 MUST 以 Governor 预算为准
- **THEN** 系统 MUST 记录相应的预算压缩或拒单原因

### Requirement: Risk budget sizing 必须输出可归因预算字段
当系统启用 Governor 模式时，预算产物 MUST 至少输出：
- `total_risk_budget`
- `sleeve_budget_used`
- `drawdown_state`
- `budget_reason_codes`

#### Scenario: 预算结果进入产物
- **WHEN** A 股实验完成并输出标准产物
- **THEN** 产物 MUST 能回答“今天的总预算为什么是这个值”
- **THEN** 产物 MUST 能回答“某个 sleeve 为什么没有吃满本地 sizing”
