## ADDED Requirements

### Requirement: research audit 必须评估 ETF 稳定器的实际部署质量
当实验包含 ETF 稳定器 V2 时，`research_audit` MUST 对 ETF sleeve 的实际部署质量给出证据，而不只看收益指标。

该证据至少 MUST 包含：
- 全窗口平均实际暴露
- 有持仓日平均暴露
- 持仓天数
- fallback 使用次数或使用日数
- under-deploy 主因摘要

#### Scenario: ETF 稳定器部署质量可追溯
- **WHEN** 研究审计生成 ETF 稳定器 V2 结论
- **THEN** 审计结果 MUST 能回答 ETF sleeve 是否真的承担了 beta 稳定器角色
- **THEN** 审计结果 MUST 能回答“收益差是因为选错规则，还是因为部署不足”

### Requirement: research audit 必须对不值得推进的 ETF 稳定器方案给出明确口径
当某个 ETF 稳定器 V2 方案在部署证据完整的前提下仍不值得推进时，`research_audit` 或实现说明 MUST 明确标记为“不建议推进”，并给出原因。

#### Scenario: 部署改善但收益风险仍不达标
- **WHEN** 某个 ETF 稳定器 V2 方案已经证明实际暴露改善，但收益/风险仍不具备推进价值
- **THEN** 研究结论 MUST 明确标记为不建议推进
- **THEN** 系统 MUST 记录其对照组与放弃理由，避免后续重复开启同类试错
