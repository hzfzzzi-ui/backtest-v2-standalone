## Apply 前人工确认清单

本文件只用于治理 apply 前确认，不自动触发 baseline 切换。

### 1. 当前建议保留的 live baseline

#### `baseline_V10_1`

- 角色：A 股个股正式主线
- `linked_exp_id`：`exp_20260328_220801073_478b`
- 个股腿绩效：`CAGR 14.49% / Sharpe 0.7039 / MaxDD -36.48% / Trades 628`
- 当前风险：linked experiment 目录当前不在 live `outputs/experiments/`，因此它暂时不是 fully reproducible active baseline
- 说明：`latest_champion.json` 当前显示的是旧 ETF research study 结果，不是 baseline canonical truth

#### `CN_STOCK_ETF_FORMAL_V1`

- 角色：正式 stock+ETF 组合主线候选
- `linked_exp_id`：`exp_20260426_005716047_8650`
- 组合绩效：`CAGR 8.20% / Sharpe 0.7775 / MaxDD -16.64%`
- ETF 腿绩效：`exp_20260426_005639325_5fc3`，`CAGR 0.55% / Sharpe 0.1224 / MaxDD -14.46%`
- 当前结论：审计通过，但收益守门未过，baseline promotion deferred

### 2. 已降级或不再作为 live baseline 的对象

- `A_STOCK_ETF_V1`
  - 当前身份：`replay_anchor`
  - `linked_exp_id`：`exp_20260420_105912701_94a3`
- `baseline_V10`
  - 当前身份：已归档到 `outputs/baselines/archive/2026-04-26/baseline_V10`
- `baseline_V10_2`
  - 当前身份：已归档到 `outputs/baselines/archive/2026-04-26/baseline_V10_2`

### 3. Apply 守门结论

在没有人工确认前，不执行下列动作：

- 不把 `CN_STOCK_ETF_FORMAL_V1` 自动升为唯一 active baseline
- 不把 `baseline_V10_1` 自动改成 `invalid` 或 `superseded`
- 不恢复或删除 `baseline_V10_1` 的 linked experiment 法源

### 4. 当前建议

- 继续保留 `baseline_V10_1` 与 `CN_STOCK_ETF_FORMAL_V1` 作为 live baseline 名义集合
- 将 `A_STOCK_ETF_V1` 保持为 replay anchor
- 后续若要正式 apply baseline 治理，先决定：
  - 是否恢复 `baseline_V10_1` 的 linked experiment 目录
  - 是否让 `CN_STOCK_ETF_FORMAL_V1` 取代个股主线，或仅作为并行组合主线
