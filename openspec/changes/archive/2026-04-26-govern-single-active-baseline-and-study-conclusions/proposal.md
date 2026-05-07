## Why

当前仓库在 baseline 法源、active baseline 唯一性、study 长期留痕三件事上仍然混在一起：

- baseline 指标真相会被 `index.json`、`latest_champion.json` 这类展示层文件干扰
- 同一时期的 baseline 治理没有显式状态机和 apply 守门
- study 结果仍可能通过 baseline append 路径沉淀成“准 baseline”资产

本变更的目标不是立刻替你决定最终保留哪条 baseline，而是先把治理规则写死、把默认行为改对，并把 apply 前人工确认项明确化。

## What Changes

- 固化 baseline 法源：正式 baseline 只认 `baseline.json.linked_exp_id`
- 固化 baseline 状态机：`active / archived / superseded / invalid / replay_anchor`
- 固化同一 `effective_period` 的唯一 active 规则
- study 默认不再 append baseline，只保留 study conclusion 记录
- compare / audit 显式暴露 baseline source-of-truth
- 在 proposal/design 中加入 apply 前人工确认清单

## Apply 前人工确认项

本 change 只定义治理规则和默认行为，不自动切换 active baseline。

真正 apply 前，必须人工确认：

- 最终保留的 active baseline 列表
- 每条 active baseline 的 `linked_exp_id`
- 个股腿绩效
- ETF 或组合腿绩效
- 其余 baseline 的降级名单

当前建议清单见同目录 [apply_confirmation.md](apply_confirmation.md)。
