## ADDED Requirements

### Requirement: positive quality factor snapshots
系统 SHALL 生成正向质量因子的日频研究快照与组合分数快照，并写出 `raw_value`、`normalized_value`、`rank_value` 与 `available` 字段。

#### Scenario: snapshots preserve provider-aligned quality matrices
- **WHEN** 研究模块构建正向质量快照
- **THEN** 系统 SHALL 直接从主线 breakout runtime context 读取对应 provider 矩阵
- **THEN** 生成的 factor score snapshot MUST 只由 catalog 中声明的质量项按权重组合而成
