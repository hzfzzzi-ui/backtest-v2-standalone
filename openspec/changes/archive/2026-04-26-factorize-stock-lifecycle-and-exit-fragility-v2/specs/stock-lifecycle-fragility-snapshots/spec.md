## ADDED Requirements

### Requirement: 生命周期 fragility 快照输出
系统 SHALL 生成与当前股票腿基线锚定一致的 lifecycle fragility factor snapshot，并记录 date、symbol、factor、raw_value、normalized_value、rank_value、availability 和 baseline lineage。

#### Scenario: 输出可审计 snapshot
- **WHEN** 运行 stock lifecycle fragility snapshot 生成流程
- **THEN** 系统 SHALL 写出按 `date + symbol + factor` 对齐的快照
- **AND** 每条记录 SHALL 包含可追溯的 baseline 锚点或 lineage 信息

### Requirement: 生命周期 fragility 组合分数快照
系统 SHALL 支持将多个 lifecycle fragility 因子聚合为 factor score snapshot，用于后续失败风险和退出条件研究。

#### Scenario: 输出 factor score snapshot
- **WHEN** 研究层对 lifecycle fragility 因子进行组合
- **THEN** 系统 SHALL 输出对应的 factor score snapshot
- **AND** 输出 SHALL 记录组成因子和组合方式
