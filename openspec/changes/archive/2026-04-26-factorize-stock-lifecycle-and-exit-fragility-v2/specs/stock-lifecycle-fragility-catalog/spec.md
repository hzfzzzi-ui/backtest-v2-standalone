## ADDED Requirements

### Requirement: 生命周期 fragility 研究目录
系统 SHALL 定义个股生命周期 fragility 与退出风险研究目录，覆盖持有期早期衰减、弱 carry、破位风险和退出条件上下文，并为每个研究对象提供清晰的语义说明与层级边界。

#### Scenario: 目录列出生命周期 fragility 因子
- **WHEN** 研究层加载 stock lifecycle fragility catalog
- **THEN** 系统 SHALL 返回一组正式注册的研究因子
- **AND** 每个因子 SHALL 标明所属分组、解释语义、可用层级和是否属于负向风险对象

### Requirement: 生命周期 fragility 因子不得伪装成正向 rank 因子
系统 MUST 允许 lifecycle fragility 因子以 failure-risk、fragility-context 或 exit-conditional 角色存在，而不是默认按 `higher is better` 解释。

#### Scenario: 因子角色被明确标记
- **WHEN** 研究目录输出某个 lifecycle fragility 因子的元数据
- **THEN** 系统 MUST 标记该因子是否为负向风险、上下文因子或退出条件因子
- **AND** 不得要求所有 lifecycle fragility 因子都支持正向排序解释
