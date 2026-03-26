## ADDED Requirements

### Requirement: ETF beta 暴露语义研究必须固定候选池并单独比较暴露参数
系统 MUST 在 `cn_etf_beta` 暴露语义研究中固定当前主候选池，不得把候选池变化与暴露参数变化绑定在同一轮主实验中。

#### Scenario: 暴露语义研究不混入候选池变化
- **WHEN** 系统创建 `cn_etf_beta` 的暴露语义研究实验
- **THEN** 该实验 MUST 固定主候选池
- **THEN** 实验变量 MUST 只包括 `target_exposure`、`min_deployable_exposure`、deployability 或 sleeve-local fallback 语义

### Requirement: ETF beta 暴露语义研究必须输出损失拆解基线
系统 MUST 为 ETF beta 暴露语义研究提供最小损失拆解口径，至少区分预算上限损失、空仓/低仓损失、fallback 替代损失与过滤/切换损失。

#### Scenario: 暴露语义研究产出损失拆解
- **WHEN** 系统完成一轮 ETF beta 暴露语义研究
- **THEN** 研究产物 MUST 能区分预算上限损失、空仓/低仓损失、fallback 替代损失与过滤/切换损失
- **THEN** 研究结论 SHALL NOT 只给出单一收益指标而不说明损失来源

### Requirement: ETF beta 暴露语义研究必须有最小 AB 结构
系统 MUST 为 ETF beta 暴露语义研究定义明确的控制组与候选组，并固定窗口、候选池和 fallback 口径。

#### Scenario: 创建最小 AB 研究方案
- **WHEN** 系统登记 ETF beta 暴露语义研究计划
- **THEN** 该计划 MUST 包含控制组与至少一个候选组
- **THEN** 该计划 MUST 固定研究窗口、候选池与 fallback 口径
