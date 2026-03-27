## ADDED Requirements

### Requirement: research audit必须解释宽基ETF主线如何在Governor边界内本地决策
当实验属于宽基 ETF 独立主线时，`research_audit` MUST 显式区分两层事实：
- Governor 提供的统一状态与风险边界
- 宽基 ETF 主线基于该边界做出的本地 enter/exit/deployability/controlled_accumulation 决策

#### Scenario: audit能区分Governor压制与主线主动不进场
- **WHEN** 某交易日宽基 ETF 主线没有形成持仓或形成较低部署
- **THEN** `research_audit` MUST 能区分是 Governor 禁做、Governor 仅给出有限带宽，还是 ETF 主线自身过滤后未入场

### Requirement: research audit必须显式审计宽基ETF承接行为
当宽基 ETF 主线在受控弱环境中维持或增加暴露时，`research_audit` MUST 记录承接是否发生、发生在哪个状态带宽、目标暴露与实际暴露是否一致，以及对应的 `reason_codes`。

#### Scenario: audit解释宽基ETF为什么在弱环境里仍有仓位
- **WHEN** 宽基 ETF 主线在 `LIGHT` 或受控 `TRANS_DOWN` 区间保留或提升暴露
- **THEN** `research_audit` MUST 显式说明这是受控承接而不是无约束抄底
- **THEN** `research_audit` MUST 暴露承接对应的状态、目标暴露、实际暴露和原因码
