## ADDED Requirements

### Requirement: ETF beta research 必须显式剔除跨境 beta

当 ETF beta sleeve 运行于本轮 domestic defense boundary research 时，系统 MUST 排除跨境 ETF，不得将其纳入国内 A 股 beta 或 defense 角色。

#### Scenario: 跨境 ETF 存在于扩展池
- **WHEN** 扩展 ETF 池包含跨境 ETF
- **THEN** 本轮 research variant MUST 将其标记为 `exclude_cross_border`
- **THEN** ETF beta selection SHALL NOT 消费这些 symbol

### Requirement: ETF beta research 弱状态必须只使用国内 beta / defense 角色

在 `TRANS_DOWN / RISK_OFF` 下，本轮 research variant SHALL 只允许国内 beta 与 defense 角色进入弱状态目标集合。

#### Scenario: 弱状态触发
- **WHEN** `effective_state_5` 属于 `TRANS_DOWN` 或 `RISK_OFF`
- **THEN** 行业主题 ETF SHALL NOT 作为弱状态默认 beta
- **THEN** 防守资产与核心国内 beta MUST 在 explain 中分开披露
