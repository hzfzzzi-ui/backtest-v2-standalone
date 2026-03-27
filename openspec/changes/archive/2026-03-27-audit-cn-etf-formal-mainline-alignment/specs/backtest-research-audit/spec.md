## ADDED Requirements

### Requirement: research audit 必须输出 ETF 正式口径对齐状态
当实验属于 `cn_etf` 或使用 `cn_etf_beta` 相关路径时，`research_audit` MUST 输出 ETF 正式口径对齐状态，并至少区分：
- `formal_mainline`
- `research_only`
- `do_not_promote`

#### Scenario: ETF 实验显示正式对齐状态
- **WHEN** 用户查看 ETF 实验的 `research_audit`
- **THEN** 审计结果 MUST 明确显示该实验属于正式主线还是研究分支

### Requirement: research audit 必须引用 ETF 正式偏离证据
当 ETF 实验不属于 `formal_mainline` 时，`research_audit` MUST 引用正式偏离证据，至少包含：
- 偏离原因列表
- 触发偏离的资产或语义对象
- 是否仍受 Governor 约束

#### Scenario: ETF 研究分支可解释为什么不能升格
- **WHEN** 某条 ETF 研究实验被标记为 `research_only` 或 `do_not_promote`
- **THEN** `research_audit` MUST 能回答它为什么不能被升格为正式主线
- **THEN** `research_audit` MUST 引用显式证据而不是仅给出抽象标签
