## ADDED Requirements

### Requirement: formal ETF stabilizer 必须暴露 BULL/TRANS_UP 的 deployment pace 诊断链

当 `cn-etf-beta-sleeve` 以 formal `strategic_beta_stabilizer` 运行时，系统 MUST 在 `BULL` 与 `TRANS_UP` 状态下显式输出同一条诊断链：`approved target`、`strategic floor target`、`tactical overlay target`、`deployment pace`、`execution path` 和 `actual exposure`。系统 SHALL NOT 只输出 `target` 与 `actual` 而省略中间 pace 语义。

#### Scenario: BULL 诊断链完整输出

- **WHEN** formal ETF stabilizer 在某个交易日的有效状态为 `BULL`
- **THEN** 系统 MUST 在正式日级产物中同时输出 `etf_target_exposure`、`etf_strategic_floor_target`、`etf_tactical_overlay_target`、`etf_deployment_pace`、`etf_execution_path` 与 `etf_actual_exposure`
- **THEN** 这些字段 MUST 共享同一份正式 contract 真相，而不是来自独立重算

#### Scenario: TRANS_UP 诊断链完整输出

- **WHEN** formal ETF stabilizer 在某个交易日的有效状态为 `TRANS_UP`
- **THEN** 系统 MUST 在正式日级产物中同时输出 `etf_target_exposure`、`etf_strategic_floor_target`、`etf_tactical_overlay_target`、`etf_deployment_pace`、`etf_execution_path` 与 `etf_actual_exposure`
- **THEN** 系统 SHALL NOT 把 `TRANS_UP` 的 pace 诊断退化成仅有 target 与 actual 的简化输出

### Requirement: formal ETF stabilizer 必须把 BULL/TRANS_UP 缺口拆成 policy、timing 与 residual

当 formal ETF stabilizer 在 `BULL` 或 `TRANS_UP` 下出现 `approved target` 与 `actual exposure` 不一致时，系统 MUST 能把缺口拆成 `pace_policy_gap`、`rebalance_timing_gap` 与 `execution_residual_gap` 三类归因，而不是只保留一个未解释的总缺口。

#### Scenario: policy gap 明确可见

- **WHEN** `deployment pace` 小于 `approved target`
- **THEN** 系统 MUST 记录对应的 `pace_policy_gap`
- **THEN** 系统 SHALL NOT 将这一差值误解释为执行失败

#### Scenario: timing gap 明确可见

- **WHEN** `deployment pace` 为正且执行路径显示当前日仍在等待月频 rebalance 或等价节奏约束
- **THEN** 系统 MUST 记录对应的 `rebalance_timing_gap`
- **THEN** 系统 SHALL NOT 将这一差值误解释为 contract 本身没有批准

#### Scenario: residual gap 明确可见

- **WHEN** `deployment pace` 已允许且不存在纯节奏等待，但实际仓位仍低于该日可执行预算
- **THEN** 系统 MUST 记录剩余的 `execution_residual_gap`
- **THEN** 系统 SHALL 为该残差保留执行链证据引用，而不是输出无来源数字
