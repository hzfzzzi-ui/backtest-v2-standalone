## MODIFIED Requirements

### Requirement: 系统必须提供候选规划正式合同
系统 MUST 在 `candidate_plan_v1` 与执行内核之间提供 `candidate_plan_v1` 正式合同。该合同 MUST 表达候选边界确认后的最终候选计划、轮换替换结果、现金感知选择结果和规划层拒绝摘要，并在排序相关字段中以 `final_score_rank` 作为 canonical 语义。

#### Scenario: 个股子系统生成候选规划合同
- **WHEN** A股个股子系统完成候选边界确认并准备进入执行内核
- **THEN** 系统 MUST 生成 `candidate_plan_v1`
- **THEN** 该 payload MUST 至少包含 `final_score_value`、`final_score_rank`、最终买入候选顺序、规划层拒绝原因计数和轮换替换摘要
- **THEN** 若同时写出 `mf_score`、`mf_rank`，它们 SHALL 只是兼容别名
