## MODIFIED Requirements

### Requirement: 正式市场状态框架必须输出状态置信度与切换原因
正式市场状态框架 SHALL 输出：
- `base_state_5`
- `effective_state_5`
- `coarse_state`
- `effective_coarse_state`
- `regime_confidence`
- `regime_duration_bars`
- `regime_transition_reason`
- `feature_availability`
- `reason_codes`

其中：
- `base_state_5` MUST 使用五状态正式主状态：
  - `BULL`
  - `TRANS_UP`
  - `LIGHT`
  - `TRANS_DOWN`
  - `RISK_OFF`
- `coarse_state` MUST 使用派生三状态：
  - `RISK_ON`
  - `NEUTRAL`
  - `RISK_OFF`
- `effective_*` MUST 允许在存在人工或策略外部干预时表达最终生效状态
- `base_*` MUST 保留模型原始状态真相

#### Scenario: 输出五状态与三状态
- **WHEN** 系统完成某一交易日的状态判定
- **THEN** 结果 MUST 同时包含五状态主状态和三状态派生视图

#### Scenario: 输出切换原因与置信度
- **WHEN** 市场状态相较上一交易日发生变化或有效状态被调整
- **THEN** 系统 MUST 记录 `regime_transition_reason`
- **THEN** 系统 MUST 记录 `regime_confidence`

#### Scenario: 存在人工或外部干预
- **WHEN** 当日存在人工或策略外部状态干预
- **THEN** 结果 MUST 同时保留 `base_state_5` 和 `effective_state_5`
- **THEN** 系统 SHALL NOT 只输出最终状态而丢失原始模型状态

## ADDED Requirements

### Requirement: 正式市场状态框架必须输出可归因子分数
正式市场状态框架 MUST 输出可归因子分数，至少包括：
- `subscores.technical`
- `subscores.sentiment`
- `subscores.macro_global`

Phase 1 中：
- `technical` MUST 作为主导状态输入
- `sentiment` SHALL 作为解释增强和弱约束
- `macro_global` SHALL 作为解释增强和弱约束

#### Scenario: 输出三类子分数
- **WHEN** 系统输出某一交易日的正式市场状态
- **THEN** 结果 MUST 可追溯到 `technical`、`sentiment` 和 `macro_global` 三类解释子分数

### Requirement: 正式市场状态框架必须提供可审计的 manual override 语义
正式市场状态框架 MUST 提供最小 `manual_override` 结构，至少包含 `active`、`reason`、`scope` 和 `actor` 或等价字段，用于解释 `effective_state_*` 相较 `base_state_*` 的变化来源。

#### Scenario: override 生效时留痕
- **WHEN** 某一交易日存在状态 override
- **THEN** 系统 MUST 记录 override 的启用标记与原因
- **THEN** 系统 MUST 允许后续审计判断状态变化是模型输出还是人工/外部干预

