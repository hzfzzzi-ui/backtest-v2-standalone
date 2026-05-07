## ADDED Requirements

### Requirement: cn_etf_beta 正式主线必须从筛票型 sleeve 收敛到 Phase 1 配置引擎
当 `cn_etf_beta` 以 `formal_mainline` 运行时，系统 MUST 将其视为 ETF Phase 1 配置引擎，而不是研究分支里的 `TopN` 排名或筛票型 beta sleeve。

#### Scenario: 正式主线不再以 TopN 作为主输出
- **WHEN** ETF 主线被标记为 `formal_mainline`
- **THEN** 结果主输出 MUST 以预算承接、三桶分配和正式 `targets` 为中心
- **THEN** `TopN`、筛票链或候选排名 SHALL NOT 作为正式主线的主语义

### Requirement: cn_etf_beta 正式主线必须显式区分权益承接、防守倾向和现金缓冲
系统 MUST 在正式 ETF 主线中显式区分权益核心承接、防守倾向迁移和现金缓冲，不得再把“无票可买”默认为正式现金状态。

#### Scenario: 正式主线显式输出现金缓冲
- **WHEN** ETF Phase 1 未将全部预算部署到 ETF 目标
- **THEN** 系统 MUST 把未部署部分显式记为 `cash_buffer_bucket`
- **THEN** 系统 MUST 提供对应原因码而不是仅以空仓结果隐式表达
