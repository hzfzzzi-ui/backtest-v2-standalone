## ADDED Requirements

### Requirement: ATR 反比调仓
系统 SHALL 支持基于 ATR 的波动率反比仓位调整：波动率越高，仓位越小。

#### Scenario: 波动率调仓公式
- **WHEN** `enable_volatility_sizing` 为 true 且买入信号触发
- **THEN** 系统 SHALL 计算目标风险金额：`risk_amount = target_order_value × vol_target_risk_pct`
- **THEN** 实际下单金额 SHALL 为：`adjusted_value = risk_amount / (atr / close)`
- **THEN** `adjusted_value` SHALL 受上下限约束：`[target_order_value × 0.3, target_order_value × 2.0]`
- **THEN** 最终数量 SHALL 按 `lot_size` 向下取整

#### Scenario: 波动率调仓默认关闭
- **WHEN** `enable_volatility_sizing` 为 false
- **THEN** 仓位计算 SHALL 使用现有等权逻辑（`nav / max_positions × order_value_scale`）

#### Scenario: ATR 不可用时降级
- **WHEN** 某标的在买入日的 ATR 值为 NaN 或 0
- **THEN** 系统 SHALL 降级使用等权仓位（不跳过买入）

### Requirement: 波动率调仓可观测性
系统 SHALL 在交易记录中输出波动率调仓的诊断信息。

#### Scenario: 交易记录包含调仓字段
- **WHEN** 波动率调仓启用且产生买入交易
- **THEN** 交易记录的 `meta_json` SHALL 包含 `vol_sizing` 对象
- **THEN** `vol_sizing` SHALL 包含 `atr`（ATR值）、`atr_pct`（ATR/close）、`raw_value`（调整前金额）、`adjusted_value`（调整后金额）

### Requirement: 前端波动率调仓配置
前端 SHALL 提供波动率调仓的开关和参数。

#### Scenario: 波动率调仓 UI
- **WHEN** 用户查看仓位配置区域
- **THEN** SHALL 显示"波动率调仓"checkbox（默认关闭）
- **THEN** 勾选后 SHALL 显示目标风险比例输入框，默认值 2%（`vol_target_risk_pct = 0.02`）
