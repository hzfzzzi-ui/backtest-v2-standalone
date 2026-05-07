## ADDED Requirements

### Requirement: study 正式留痕必须收敛为简短结论
系统 MUST 将 study 的正式长期留痕收敛为研究结论，而不是并行 baseline。study 正式输出 MUST 至少包含 `study_id`、`compared_baseline_id`、`verdict`、`summary_short`、`exp_id`、`window_key`、`variant_name` 与关键指标摘要。

#### Scenario: study 证实一个研究方向
- **WHEN** 某个 study 在既定窗口与变体上完成执行并通过研究判定
- **THEN** 系统 MUST 记录一条简短结论，说明该方向被 `confirmed`
- **THEN** 该结论 MUST 引用所对照的 baseline 与实验证据
- **THEN** 系统 SHALL NOT 仅因为该 study 结果较优，就把 study 本身持久化为并行 baseline

#### Scenario: study 证伪一个研究方向
- **WHEN** 某个 study 被判定为 `falsified`
- **THEN** 系统 MUST 记录一条简短结论，说明该方向不可靠或不值得继续推进
- **THEN** 系统 MAY 保留实验产物用于追溯
- **THEN** 系统 SHALL NOT 把失败 study 的人类报告继续当作 baseline 候选资产

#### Scenario: study 暂无定论
- **WHEN** 某个 study 缺少足够证据，或法源 baseline 当前不可复核
- **THEN** 系统 MUST 允许 `inconclusive` 结论
- **THEN** 该结论 MUST 明确说明不确定原因

### Requirement: study baseline 只用于对照，不得提升为资产入口或正式锚点
系统 SHALL NOT 继续让 study 通过 report append、latest champion 或其他路径获得与 baseline 平级的正式地位。study 中声明的 `baseline_id` 只用于研究对照。

#### Scenario: study 输出优于当前 baseline
- **WHEN** 某个 study 的实验结果优于当前 active baseline
- **THEN** 系统 MAY 记录该方向被证实或值得进一步评估
- **THEN** 系统 SHALL NOT 自动把该 study 或其 exp 变成新的 active baseline
- **THEN** baseline 切换 MUST 走单独的 baseline 治理流程与人工确认
