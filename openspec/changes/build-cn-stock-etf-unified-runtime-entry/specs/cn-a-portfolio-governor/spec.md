## ADDED Requirements

### Requirement: Governor 必须在统一运行中同时裁决股票与 ETF sleeve 预算
当实验属于 `cn-stock-etf-unified-runtime-entry` 时，`global_portfolio_governor` MUST 在同一次实验内同时裁决 `cn_stock_trend_alpha_core` 与 `cn_etf_beta` 的预算、部署上限与预算原因码。Governor SHALL NOT 只给出组合级总预算而不暴露两条 sleeve 的分配结果。

#### Scenario: Governor 统一下发两条 sleeve 预算
- **WHEN** 统一运行实验进入建仓或调仓阶段
- **THEN** Governor MUST 同时输出股票 alpha sleeve 与 ETF beta sleeve 的 `sleeve_budgets`
- **THEN** 每条 sleeve 的部署结果 MUST 可回溯到同一组组合级预算真相

#### Scenario: 单条 sleeve 因预算被压缩
- **WHEN** 统一运行实验中某条 sleeve 未吃满理论预算
- **THEN** Governor MUST 暴露对应的 `budget_reason_codes` 或等价字段
- **THEN** 系统 MUST 能区分“组合级预算不足”和“该 sleeve 自身不可部署”两类原因
