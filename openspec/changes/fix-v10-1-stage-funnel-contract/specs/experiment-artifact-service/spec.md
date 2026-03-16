## ADDED Requirements

### Requirement: artifact service 必须保留 stage_funnel 可用性语义
当核心 artifact service 生成 `stage_funnel` lazy section 或 `run_meta.counters.buy_stage_funnel` 时，系统 MUST 原样保留阶段可用性语义。对于没有可靠计数来源的阶段，artifact service MUST 输出 `available=false`，并将对应的 `input_count`、`output_count`、`filtered_count` 保持为 `null`。对于有正式来源且真实计数为 `0` 的阶段，artifact service MUST 保持 `available=true` 且数值为 `0`。

#### Scenario: 聚合 unavailable 阶段
- **WHEN** 上游 `daily_row` 或正式诊断来源无法为某个漏斗阶段提供可靠计数
- **THEN** artifact service SHALL 在 `stage_funnel` 与 `run_meta.counters.buy_stage_funnel` 中将该阶段标记为 `available=false`
- **THEN** artifact service SHALL NOT 将该阶段计数补写为 `0`

#### Scenario: 聚合真实零值阶段
- **WHEN** 上游正式来源明确给出某个漏斗阶段的真实计数为 `0`
- **THEN** artifact service SHALL 保留该阶段 `available=true`
- **THEN** artifact service SHALL 在聚合结果中输出数值 `0`

#### Scenario: lazy section 与 run_meta 语义一致
- **WHEN** 同一个实验同时生成 `stage_funnel` lazy section 与 `run_meta.counters.buy_stage_funnel`
- **THEN** 两个输出面的 `available`、`input_count`、`output_count`、`filtered_count` 语义 SHALL 保持一致
- **THEN** 前端消费任一路径都 SHALL 得到相同的 unavailable/zero 判断结果
