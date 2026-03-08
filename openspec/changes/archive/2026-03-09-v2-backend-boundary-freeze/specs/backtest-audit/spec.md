## ADDED Requirements

### Requirement: 审计产物必须由共享 contract 归一化
系统 SHALL 使用共享审计 contract 组装 `stage_summary`、`stage_pipeline`、`audit.json` 与相关 `run_meta` 摘要。foundation shell 与 artifact stabilize MUST 通过同一 helper 保持口径一致。

#### Scenario: foundation shell 输出阶段摘要
- **WHEN** foundation shell 完成一次回测执行
- **THEN** 它输出的阶段摘要可被共享审计 contract 直接归一化，而不需要第二套 ad-hoc 映射逻辑

#### Scenario: artifact stabilize 写出统一 audit.json
- **WHEN** `stabilize_experiment_result` 写入实验目录
- **THEN** `audit.json`、`stage_summary`、`manifest stage metadata` 来自同一共享 contract，且字段口径一致
