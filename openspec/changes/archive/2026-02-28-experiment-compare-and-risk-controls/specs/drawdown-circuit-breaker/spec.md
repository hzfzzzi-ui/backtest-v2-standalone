## ADDED Requirements

### Requirement: 回撤熔断暂停开仓
系统 SHALL 支持组合级回撤熔断：当组合回撤超过阈值时暂停所有新开仓。

#### Scenario: 回撤触发熔断
- **WHEN** `enable_drawdown_breaker` 为 true 且当前组合回撤（从峰值回落比例） ≥ `drawdown_breaker_pct`（如 0.15 表示 -15%）
- **THEN** 系统 SHALL 进入熔断状态，拒绝所有新买入信号
- **THEN** 已有持仓的退出规则 SHALL 继续正常执行（不影响卖出）

#### Scenario: 熔断恢复
- **WHEN** 组合回撤恢复到 ≤ `drawdown_breaker_recover_pct`（如 0.10 表示 -10%）
- **THEN** 系统 SHALL 解除熔断状态，恢复正常买入

#### Scenario: 熔断默认关闭
- **WHEN** `enable_drawdown_breaker` 为 false
- **THEN** 回撤熔断 SHALL 不参与买入决策

#### Scenario: 熔断中的买入信号处理
- **WHEN** 熔断期间产生买入信号
- **THEN** 该信号 SHALL 被跳过（不下单）
- **THEN** 跳过计数器 `drawdown_breaker_block_count` SHALL +1

### Requirement: 回撤熔断计数器
系统 SHALL 输出熔断相关的诊断计数器。

#### Scenario: 计数器写入 run_meta
- **WHEN** 回测完成
- **THEN** `run_meta.json` 的 `counters` SHALL 包含 `drawdown_breaker_block_count`（整数，被熔断拦截的买入信号数）
- **THEN** `counters` SHALL 包含 `drawdown_breaker_trigger_count`（整数，熔断触发次数）
- **THEN** `counters` SHALL 包含 `drawdown_breaker_recover_count`（整数，熔断恢复次数）

### Requirement: 前端回撤熔断配置
前端 SHALL 提供回撤熔断的参数配置。

#### Scenario: 回撤熔断 UI
- **WHEN** 用户查看风控配置区域
- **THEN** SHALL 显示"回撤熔断"checkbox（默认关闭）
- **THEN** 勾选后 SHALL 显示触发阈值（默认 15%）和恢复阈值（默认 10%）输入框
