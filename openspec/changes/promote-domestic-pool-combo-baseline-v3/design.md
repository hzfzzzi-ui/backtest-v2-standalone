## Decision

### 1. V3 绑定对象

V3 只绑定三窗口审计中的全周期 `1226` 组合实验：

- baseline id: `CN_STOCK_ETF_COMBO_BASELINE_V3`
- linked exp: `exp_20260510_034302669_7790`
- study round: `sr_20260510_domestic_pool_three_window_audit`
- variant: `DOMESTIC_POOL_BASE`
- effective start: `2012-07-12`

不用 `1217` 或 `1626` 作为 baseline truth，因为它们不是完整 live baseline 生效期。

### 2. 状态切换

同一 `effective_period = cn_a_multi_sleeve:2012-2026` 只保留 V3 为 active：

- `CN_STOCK_ETF_COMBO_BASELINE_V3`: `active`
- `CN_STOCK_ETF_FORMAL_V1`: `superseded`
- `CN_STOCK_ETF_COMBO_BASELINE_V2`: `superseded`

旧 baseline 目录不删除，保留回滚路径。

### 3. 可回退方式

若 V3 后续审计失败，回退路径是：

1. 将 `CN_STOCK_ETF_COMBO_BASELINE_V3.status` 改为 `superseded` 或 `invalid`。
2. 将 `CN_STOCK_ETF_FORMAL_V1.status` 或 `CN_STOCK_ETF_COMBO_BASELINE_V2.status` 改回 `active`。
3. 刷新 `outputs/baselines/index.json`。
4. 将前端默认 bootstrap 和 regression contract 恢复到对应 baseline。

### 4. 风险接受

V3 晋升接受一个明确风险：`1217/1626` 的 registry delta 不是严格 same-window compare。但用户已明确要求直接提升，因此本次以 `1226` 全周期同起点结果作为 baseline truth，三窗口结果作为支持性证据。
