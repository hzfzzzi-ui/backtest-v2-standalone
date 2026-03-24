## ADDED Requirements

### Requirement: cn_etf 研究入口必须支持正式ETF beta sleeve语义
当 `cn_etf` 被 A 股 governed multi-sleeve 主线消费时，系统 MUST 将 `cn_etf` 研究入口明确标记为 `cn_etf_beta` 的正式来源之一，而 SHALL NOT 继续把它仅视为孤立的 ETF research entry。

#### Scenario: ETF 研究入口进入 governed 主线
- **WHEN** Governor 启用 `cn_etf_beta` sleeve
- **THEN** 系统 MUST 允许从 `cn_etf` 研究入口解析正式 ETF beta 候选池
- **THEN** 相关产物 MUST 将该入口标识为 beta sleeve 来源而不是独立旁路实验

### Requirement: cn_etf 研究入口必须暴露Phase 1 core beta范围
当 `cn_etf` 服务于 `cn_etf_beta` Phase 1 时，研究入口 MUST 显式暴露 core beta 范围：
- `510300.SH`
- `510500.SH`
- `510050.SH`
- `512100.SH`

并 MAY 显式暴露 `512890.SH` 为 limited defense candidate。

#### Scenario: 研究入口返回 core beta 范围
- **WHEN** 系统为 `cn_etf_beta` 构建 Phase 1 候选池
- **THEN** 入口摘要 MUST 明确哪些 ETF 属于正式 core beta 范围
- **THEN** 入口摘要 MUST 明确 `512890.SH` 是否作为 limited defense candidate 参与

