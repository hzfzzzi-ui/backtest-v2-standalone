## ADDED Requirements

### Requirement: 生命周期 / 退出风险研究入口
系统 SHALL 提供 stock lifecycle fragility study surface，支持基于当前股票腿主线基线的三窗口研究。

#### Scenario: 三窗口 lifecycle 研究
- **WHEN** 用户运行 stock lifecycle fragility real mainline study
- **THEN** 系统 SHALL 产出 `1217`、`1222`、`1226` 三窗口研究结果
- **AND** 结果 SHALL 保持与当前股票腿基线锚点一致

### Requirement: 失败风险与退出条件分析
系统 SHALL 支持 lifecycle fragility 因子对失败风险、退出条件分布和 veto 改善度的研究输出。

#### Scenario: 输出失败风险分析
- **WHEN** 研究层分析 lifecycle fragility 因子
- **THEN** 系统 SHALL 能输出失败风险 bucket、退出条件分布或 veto 改善指标中的至少一种
- **AND** 输出 MUST 明确该研究结果属于 `RESEARCH_ONLY`

### Requirement: 研究面不得改变主线默认行为
系统 MUST 将 lifecycle fragility study surface 限制在研究层，不得在本能力中直接改变正式主线 runtime、退出规则或排序行为。

#### Scenario: 研究运行不污染主线
- **WHEN** 用户运行 stock lifecycle fragility 研究
- **THEN** 系统 MUST 只生成研究产物
- **AND** 不得改变正式主线默认配置或交易行为
