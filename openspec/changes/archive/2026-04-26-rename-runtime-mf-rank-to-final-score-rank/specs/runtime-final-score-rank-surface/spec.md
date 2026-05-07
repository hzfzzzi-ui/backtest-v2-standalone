## ADDED Requirements

### Requirement: runtime MUST expose canonical `final_score_rank` semantics
系统 MUST 将当前候选排序、topk 截断和 rank tilt 的正式 runtime 语义定义为 `final_score_rank`，并 SHALL NOT 再把该语义仅通过 `mf_rank` 对外暴露。

#### Scenario: candidate audit writes canonical rank fields
- **WHEN** 系统为任一候选写出 candidate audit 行
- **THEN** 产物 MUST 写出 `final_score_value` 与 `final_score_rank`
- **THEN** 若保留 `mf_score` 与 `mf_rank`，它们 SHALL 只是兼容别名

#### Scenario: debug plan writes canonical rank counters
- **WHEN** 系统生成 `debug_plan`
- **THEN** 其排序与 gate 诊断 MUST 写出 `final_score_rank_triggered`、`final_score_rank_applied`、`final_score_rank_gate_on`
- **THEN** 旧 `mf_rank*` 字段 MAY 保留，但 SHALL NOT 再是唯一正式字段

### Requirement: diagnostics MUST prefer canonical rank counters with legacy fallback
聚合诊断、artifact diagnostics 与 daily accounting MUST 优先消费 `final_score_rank*` 字段；若新字段缺失，系统 MAY 回退读取旧 `mf_rank*` 字段。

#### Scenario: new experiment outputs diagnostics
- **WHEN** 新产物包含 `final_score_rank*` 字段
- **THEN** 聚合 counters MUST 以这些字段为真相

#### Scenario: old experiment remains readable
- **WHEN** 历史产物只包含 `mf_rank*` 字段
- **THEN** 聚合 counters MUST 仍能生成等价结果
