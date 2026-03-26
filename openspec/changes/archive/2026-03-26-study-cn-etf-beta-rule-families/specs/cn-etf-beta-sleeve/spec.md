## ADDED Requirements

### Requirement: 当前 ETF V1 规则必须被标记为正式对照组
系统 MUST 将当前 `cn_etf_beta` V1 规则标记为 ETF 规则族研究的正式对照组，而不是默认终点。

该对照组至少包含：
- `MA120` 绝对过滤
- `60/120 日` 相对强弱排序
- 周频调仓

#### Scenario: ETF 研究引用当前 V1 规则
- **WHEN** 系统创建任一 ETF 规则族 AB 研究
- **THEN** 当前 V1 规则 MUST 可被明确引用为对照组
- **THEN** 系统 SHALL NOT 把 V1 规则自动等同为正式最优策略

### Requirement: ETF beta 正式研究必须优先比较 dual momentum 家族
系统 MUST 将 `Dual Momentum 基础版` 视为 ETF beta 正式研究的第一优先规则族。

该规则族 MUST 同时包含：
- 相对动量选择
- 绝对动量过滤
- 明确的风险资产 fallback 口径

#### Scenario: 开启 ETF beta 下一阶段主研究
- **WHEN** 系统创建下一阶段 ETF beta 正式研究
- **THEN** 第一条研究线 MUST 属于 dual momentum 家族
- **THEN** 系统 SHALL NOT 先跳到更复杂的 vol target 或更大 ETF 候选池
