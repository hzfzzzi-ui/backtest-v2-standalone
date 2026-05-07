## Context

当前账户层、统一状态切换合同、shared execution owner 都已经完成。当前结构基线是 `sell-first` 正向、`defense establish` 行为已真实落地，但收益端回吐，说明问题收敛到 `defense establish` 的频率与延续，而不是 owner 或 explain。

## Goals / Non-Goals

**Goals:**
- 在不改变当前结构真相的前提下，为 `defense establish` 增加最小可解释参数化。
- 允许比较至少两组行为变体：当前全 defensive 边界建仓，和更收敛的 `RISK_OFF-only` 建仓。
- 让 runtime / audit 能看到当前生效的建仓研究变体。

**Non-Goals:**
- 不改账户层 owner。
- 不改 `sell-first` 释放现金主行为。
- 不改 `stock alpha`、`TRANS_DOWN` 顶层预算、regime 定义。
- 不在这轮引入新的恢复态行为家族重写。

## Decisions

1. 只把 `defense establish` 参数化，不再继续改结构层。
   - 原因：当前收益侧问题来自建仓行为，不是 owner 或 explain。
   - 备选方案：继续改 transition contract。否决，因为结构层已收口。

2. 第一批 A/B 只研究两个维度：触发边界、是否允许 top-up。
   - 触发边界：`TRANS_DOWN + RISK_OFF` vs `RISK_OFF-only`
   - top-up：允许 vs 不允许
   - 原因：这两个变量最直接影响持仓连续性，且改动最小。

3. A/B 通过共享账户 transition policy 变体运行，而不是再走局部 patch。
   - 原因：保持单一真相，避免再次引入执行层双语义。

## Risks / Trade-offs

- [风险] `RISK_OFF-only` 可能降低弱势非零持仓率 → 缓解：与当前版本对比 `RISK_OFF nonzero_rate` 和收益侧指标。
- [风险] 禁用 top-up 可能使防守仓太薄 → 缓解：保留 `sell-first-only` 与当前版本作为两端对照。
- [风险] 研究变体过多导致归因变差 → 缓解：只跑最小矩阵，不同时引入恢复态新逻辑。
