## Context

这个 change 处理的是治理边界，不改研究时点、不改组合逻辑，也不自动 apply baseline 切换。

要解决的问题只有三类：

1. baseline 真相只能来自 linked experiment
2. active baseline 需要状态机和唯一性约束
3. study 的正式长期留痕应该是 verdict 记录，而不是 baseline-style append

## Decisions

### Decision 1: baseline source-of-truth 只认 linked experiment

- `baseline.json.linked_exp_id` 是 baseline 的唯一正式法源
- `index.json`、`latest_champion.json`、human digest 都只是展示层
- compare / audit 必须显式说明这一点

### Decision 2: active baseline 用状态机管理

正式 baseline 采用：

- `active`
- `archived`
- `superseded`
- `invalid`
- `replay_anchor`

并要求同一 `effective_period` 最多一个 `active`。

### Decision 3: study 默认只写 conclusion registry

- `study_run` 默认不 append baseline
- 默认只写 study conclusion 最小留痕
- 如需兼容旧链路，baseline append 只能显式 opt-in，且不得改变 study 的治理身份

### Decision 4: apply 仍是人工决策

这次实现不会自动把任何 baseline 升格、降级或 invalid 掉。

真正 apply 前必须先人工确认：

- 保留哪些 active baseline
- 它们各自的 `linked_exp_id`
- 个股腿绩效
- ETF/组合腿绩效
- 其他 baseline 的降级名单

## Data Model

### Baseline record

- `baseline_id`
- `status`
- `effective_period`
- `linked_exp_id`
- `execution_contract_ref`
- `baseline_source_of_truth`
- `superseded_by`

### Study conclusion record

- `study_id`
- `compared_baseline_id`
- `verdict`
- `summary_short`
- `exp_id`
- `window_key`
- `variant_name`
- `key_metrics`
- `baseline_source_of_truth`

## Risks

- 现有 `baseline_V10_1` 的 linked experiment 当前不在 live `outputs/experiments` 中，意味着 apply 时不能把它当 fully reproducible baseline 直接通过
- 历史工具链仍可能读取 `latest_champion.json` 或 baseline ledger，需要把这些路径明确降格为 display/compat 层
- `study` 默认行为切换后，旧脚本或旧认知可能误以为 baseline append “失效”，实际上它只是变成了显式 opt-in

## Verification

- 定向单测覆盖 `study_run` 默认不 append baseline
- 定向单测覆盖 study conclusion registry 写入
- 定向单测覆盖 baseline active 唯一性约束
- 定向单测覆盖 compare 输出 `baseline_source_of_truth` 与 `latest_champion` 冲突检测
- apply 前人工确认清单见 [apply_confirmation.md](apply_confirmation.md)
