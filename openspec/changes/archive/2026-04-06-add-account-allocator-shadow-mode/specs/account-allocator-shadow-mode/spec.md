# account-allocator-shadow-mode Specification

## Purpose

定义账户配置中枢的 shadow mode，使账户层在不接管执行的前提下，输出建议预算、偏差解释与状态切换建议。

## Requirements

### Requirement: shadow mode 必须输出建议预算但不得接管执行

系统 SHALL 输出账户层建议预算，但 SHALL NOT 直接改写当前 runtime 的真实下单行为。

#### Scenario: 生成 shadow budget
- **WHEN** runtime 完成状态和库存摘要计算
- **THEN** 系统生成 suggested defense / core beta / alpha budgets
- **THEN** 当前 stock / ETF 执行路径保持不变

### Requirement: shadow mode 必须暴露建议与实际的偏差

系统 SHALL 在 explain surface 中同时给出 suggested budgets、actual budgets 和 deviation reasons。

#### Scenario: 读取账户级 explain
- **WHEN** 用户查看 runtime explain 或 `run_meta`
- **THEN** 能看到 suggested budgets
- **THEN** 能看到 actual budgets 和 deviation reasons

### Requirement: shadow mode 必须可作为后续预算上收的基线

系统 SHALL 让 shadow mode 的输出可被后续预算上收 change 直接复用。

#### Scenario: 后续 change 复用 shadow 输出
- **WHEN** 后续 change 接管账户预算权
- **THEN** 可直接复用 shadow mode 的预算语义与字段命名
