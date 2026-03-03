# risk-budget-sizing Specification

## Purpose
系统化风险预算仓位管理 — 从组合风险到单笔仓位的自上而下分配框架，包含渐进式回撤保护。

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
