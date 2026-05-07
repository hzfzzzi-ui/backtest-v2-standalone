# study-conclusion-registry Specification

## Purpose

定义 study 的最小长期留痕格式，让研究结果保留为可追溯的 verdict 记录，而不是并行 baseline。

## Requirements

### Requirement: every formal study run MUST append a conclusion record

正式 study 每完成一次 window/variant 执行，都 MUST 追加一条结论记录。

#### Scenario: confirmed study direction

- **WHEN** 某个 study 在既定 window 和 variant 上完成执行，且研究结论支持该方向
- **THEN** 系统 MUST 记录一条 `confirmed` 结论
- **THEN** 该记录 MUST 引用 compare baseline 和证据实验

#### Scenario: falsified study direction

- **WHEN** 某个 study 被判定为不可靠或不值得继续推进
- **THEN** 系统 MUST 记录一条 `falsified` 结论
- **THEN** 系统 SHALL NOT 因为保留了实验产物，就把该 study 视为 baseline 候选

#### Scenario: inconclusive study direction

- **WHEN** 研究证据不足，或 compare baseline 当前不可 fully reproduce
- **THEN** 系统 MUST 允许记录 `inconclusive` 结论
- **THEN** 记录 MUST 明确保留不确定性

### Requirement: conclusion records MUST have a minimal stable schema

study conclusion 的正式记录 MUST 至少包含：

- `study_id`
- `compared_baseline_id`
- `verdict`
- `summary_short`
- `exp_id`
- `window_key`
- `variant_name`
- `key_metrics`

#### Scenario: read a conclusion record

- **WHEN** 调用方读取任意 study conclusion
- **THEN** 调用方 MUST 能直接识别其 compare baseline、核心 verdict 和关键指标摘要

### Requirement: conclusion registry MUST preserve baseline source-of-truth metadata

若 conclusion 来自有 compare baseline 的正式 study，registry SHOULD 一并保留 baseline source-of-truth 元数据，避免展示层数值覆盖 linked experiment 法源。

#### Scenario: baseline compare has a display-layer conflict

- **WHEN** compare baseline 的 display-layer 指标与 linked experiment 冲突
- **THEN** 结论记录 SHOULD 保留 source-of-truth 说明
- **THEN** 调用方 SHALL NOT 把 display-layer 数值当作 canonical baseline truth
