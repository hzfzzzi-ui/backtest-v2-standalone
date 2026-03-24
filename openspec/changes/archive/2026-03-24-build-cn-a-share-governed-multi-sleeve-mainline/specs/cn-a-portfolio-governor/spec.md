## ADDED Requirements

### Requirement: A股子系统必须存在唯一合法的总风险预算层
系统 MUST 为 A 股子系统提供唯一合法的 `cn-a-portfolio-governor` 合同，用于统一消费 `market_regime_engine`、回撤状态、恢复/冷却状态和 sleeve 当前暴露，并输出全组合总风险预算与 sleeve 预算。任何单一 sleeve SHALL NOT 直接定义或覆盖全组合总风险预算。

#### Scenario: Governor 生成全组合预算
- **WHEN** A 股子系统完成某一交易日的状态判定与组合状态汇总
- **THEN** Governor MUST 输出 `total_risk_budget`
- **THEN** Governor MUST 输出 `total_exposure_cap`
- **THEN** Governor MUST 输出按 sleeve 划分的 `sleeve_budgets`

#### Scenario: sleeve 不得绕过 Governor 改写总预算
- **WHEN** `cn_stock_trend_alpha_core` 或 `cn_etf_beta` 运行各自的本地 sizing 逻辑
- **THEN** 这些 sleeve MUST 只消费 Governor 下发的预算
- **THEN** 这些 sleeve SHALL NOT 直接把全组合风险预算改写为新的全局真相

### Requirement: Governor 必须统一 drawdown ladder 与恢复状态
`cn-a-portfolio-governor` MUST 统一管理 A 股子系统的 drawdown ladder、recovery state、cooldown state 和 defense floor。Governor SHALL 允许不同 sleeve 在预算内做本地执行，但 MUST 保持 drawdown 与恢复规则对全组合一致。

#### Scenario: 回撤进入更严格档位
- **WHEN** 当前组合回撤穿越 Governor 配置的更高风险档位
- **THEN** Governor MUST 重新计算 `total_risk_budget`
- **THEN** Governor MUST 相应压缩受影响 sleeve 的 `sleeve_budgets`

#### Scenario: 组合处于冷却或恢复阶段
- **WHEN** Governor 判断组合处于 `cooldown` 或 `recovery` 阶段
- **THEN** Governor MUST 在预算输出中显式暴露该状态
- **THEN** 下游 sleeve MUST 基于该状态调整开仓和恢复节奏

### Requirement: Governor 必须输出最小可归因预算证据链
每次启用 Governor 的 A 股运行 MUST 输出最小预算证据链，至少包括 `portfolio_budget`、`sleeve_budgets`、`drawdown_state`、`recovery_state`、`cooldown_state` 和 `governor_reason_codes`，并允许 `run_meta.json`、`audit.json` 与工作台 snapshot 统一引用。

#### Scenario: Governor 运行后可审计
- **WHEN** A 股子系统运行完成
- **THEN** 产物 MUST 能回答“今天为什么总仓位是这个水平”
- **THEN** 产物 MUST 能回答“今天为什么某个 sleeve 被压缩或停用”

