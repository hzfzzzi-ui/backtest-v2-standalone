## ADDED Requirements

### Requirement: 研究审计必须评估 ETF sleeve 是否真实部署
系统 MUST 在 ETF 研究审计中评估 `cn_etf_beta` 是否真实部署，而不只检查订单和交易是否存在。

#### Scenario: ETF 研究审计检查暴露质量
- **WHEN** 系统完成 ETF beta 研究实验
- **THEN** 审计 MUST 至少输出平均实际暴露、有持仓日平均暴露与 deployability gap
- **THEN** 审计 SHALL NOT 仅凭 `orders > 0` 或 `trades > 0` 判定部署有效

### Requirement: 研究审计必须输出 ETF sleeve 的 under-deploy 归因摘要
系统 MUST 为 ETF beta 研究审计输出 under-deploy 原因分布与 fallback 使用摘要。

#### Scenario: ETF 审计输出部署不足摘要
- **WHEN** ETF sleeve 存在长期低暴露或频繁未部署
- **THEN** 审计 MUST 输出 `under_deploy_reason_counts` 或等价摘要
- **THEN** 审计 MUST 输出 fallback 使用频次或占比
