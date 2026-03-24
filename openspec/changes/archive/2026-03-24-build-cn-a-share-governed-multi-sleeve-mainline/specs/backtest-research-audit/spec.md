## ADDED Requirements

### Requirement: research audit 必须引用A股统一归因证据链
当实验属于 A 股 governed multi-sleeve 主线时，`backtest-research-audit` MUST 引用 `market_regime_engine`、`global_portfolio_governor`、各 sleeve 和 `manual_override` 的统一 attribution 证据，而 SHALL NOT 只引用孤立的收益或执行产物。

#### Scenario: A股 governed 实验引用 attribution 证据
- **WHEN** 实验运行属于 A 股 governed multi-sleeve 口径
- **THEN** `research_audit.evidence_refs` MUST 引用 regime、budget、sleeve 和 override 相关证据

### Requirement: research audit 必须能回答仓位与状态来源
当实验属于 A 股 governed multi-sleeve 主线时，research audit MUST 允许回答以下问题：
- 今天的生效状态来自哪里
- 今天的预算变化来自哪里
- 某个 sleeve 为什么被压缩或停用
- 是否存在人工 override

#### Scenario: 审计结论可解释仓位变化
- **WHEN** 用户查看 governed 主线实验的 research audit
- **THEN** audit MUST 能定位到相应的状态、预算和 sleeve 证据
- **THEN** audit SHALL NOT 只给出最终 PASS/WARN/FAIL 而没有可追溯来源

