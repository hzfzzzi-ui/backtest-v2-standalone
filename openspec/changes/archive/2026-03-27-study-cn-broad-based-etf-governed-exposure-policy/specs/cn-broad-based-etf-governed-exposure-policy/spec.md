## ADDED Requirements

### Requirement: 宽基 ETF sleeve 必须在同一 Governor 下使用独立暴露政策
系统 MUST 提供 `cn-broad-based-etf-governed-exposure-policy` 能力，用于在统一 Governor 真相下为宽基 ETF sleeve 定义独立于个股 alpha 的本地暴露翻译。该能力 MUST 使用 Governor 输出的 canonical 5-state 作为唯一状态真相源，但 SHALL NOT 默认复用个股 alpha 的快速收缩规则。

#### Scenario: 宽基 ETF 继续服从 Governor
- **WHEN** 宽基 ETF sleeve 计算当日目标暴露
- **THEN** 它 MUST 使用 Governor 的 `effective_state_5`、总风险预算与相关预算约束作为上游输入
- **THEN** 它 SHALL NOT 自行重建第二套环境状态机

#### Scenario: 宽基 ETF 不再沿用个股 alpha 式收缩
- **WHEN** 宽基 ETF sleeve 处于 `LIGHT` 或受控 `TRANS_DOWN` 环境
- **THEN** 系统 MUST 允许其使用不同于个股 alpha 的本地暴露翻译
- **THEN** 该翻译 MUST 被显式记录为宽基 ETF 配置层语义，而不是隐式继承个股 alpha 逻辑

### Requirement: 宽基 ETF 暴露政策必须支持分层承接与 fallback 语义
宽基 ETF 暴露政策 MUST 同时定义 `target_exposure`、`min_deployable_exposure`、`layering_policy` 与 `fallback_policy`。该政策 MUST 允许宽基 ETF 在 `LIGHT` 与受控 `TRANS_DOWN` 状态下保留或分层承接宽基 beta，但在 `RISK_OFF` 下 MUST 回到极低或零暴露。

#### Scenario: 受控弱环境下允许分层承接
- **WHEN** Governor 输出 `LIGHT` 或受控 `TRANS_DOWN`
- **THEN** 宽基 ETF sleeve MAY 按分层承接规则保留或增加一部分宽基 beta 暴露
- **THEN** 系统 MUST 对该行为给出明确的 `layering_band` 或等价分层证据

#### Scenario: 极端风险状态下不允许继续承接
- **WHEN** Governor 输出 `RISK_OFF`
- **THEN** 宽基 ETF sleeve MUST 回到极低或零暴露
- **THEN** 系统 SHALL NOT 把 `RISK_OFF` 解释成继续分层吸纳宽基 beta 的许可

### Requirement: 宽基 ETF 暴露政策研究必须输出最小 AB 证据
系统 MUST 为宽基 ETF 暴露政策提供最小研究对照，至少比较不同 `target_exposure / min_deployable_exposure / layering / fallback` 组合，并输出可复现的研究摘要。

#### Scenario: 最小研究 AB 可复现
- **WHEN** 用户运行宽基 ETF governed exposure policy 研究
- **THEN** 产物 MUST 能区分控制组与各暴露政策变体
- **THEN** 产物 MUST 显式暴露每个变体的目标暴露、实际暴露、fallback 使用与 under-deploy 原因
