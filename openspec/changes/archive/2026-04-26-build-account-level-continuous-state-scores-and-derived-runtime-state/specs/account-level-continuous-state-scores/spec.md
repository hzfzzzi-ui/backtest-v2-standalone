## ADDED Requirements

### Requirement: 账户层连续状态分数目录
系统 SHALL 定义账户层连续状态分数目录，首版至少包含 `risk_on_score`、`recovery_score`、`defense_score` 三个 score，并为每个 score 明确中文说明、适用范围、as-of 约束、标准化约定和解释边界。

#### Scenario: score 目录可独立声明研究合同
- **WHEN** 研究模块加载账户层连续状态分数目录
- **THEN** 系统 SHALL 返回首版 3 个 score 的固定标识、元数据字段和说明文本

#### Scenario: score 目录包含可审计字段
- **WHEN** 任一 score 被声明到目录中
- **THEN** 该 score SHALL 同时声明 `score_id`、中文说明、scope、标准化约定、asof 约束和解释边界
