## Why

用户已明确要求把组合主线也升级到 V4，并且上下文已经先将 A 股 stock 正式 baseline 重挂到 D7 deep-only。

当前最接近这一要求的同合同组合候选是：

- study: `cn_stock_etf/cn_stock_etf_high_chase_d5_deep_mae_combo_ab_v1`
- full-cycle variant: `HC_D5_DEEP_ONLY_IMMEDIATE_COMBO`
- linked exp: `exp_20260511_073506050_3d22`

这条候选并不是按 combo headline 指标自动胜出的版本。它的价值主要来自：

1. 与刚刚升格的 stock baseline D7 deep-only 保持规则一致。
2. 三窗口中 stock 腿回撤修复是成立的。
3. 用户接受这次 promotion 作为人工 override，而不是“收益显著胜出”的自动结论。

因此这次工作不是再做研究结论，而是把用户明确接受的组合候选登记为新的正式 combo baseline V4，并保留 V3 作为可回滚锚点。

## What Changes

- **BREAKING**: 当前正式组合主线从 `CN_STOCK_ETF_COMBO_BASELINE_V3` 切换为 `CN_STOCK_ETF_COMBO_BASELINE_V4`。
- 新基线绑定 `linked_exp_id = exp_20260511_073506050_3d22`。
- `CN_STOCK_ETF_COMBO_BASELINE_V3` 标记为 `superseded`，保留目录与 linked experiment 作为回滚锚点。
- 前端默认 bootstrap baseline 与 foundation regression current anchor 切换到 V4。

## Capabilities

### Modified Capabilities

- `baseline-anchor-registration`: 允许在用户明确批准后，将 D7 deep-only 组合候选登记为新的正式 combo baseline V4。
- `script-surface-governance`: 要求这次 promotion 同步写入 baseline 台账、promotion note 和 latest champion。

## Impact

- 影响 `outputs/baselines/` 中 combo active baseline 注册状态。
- 影响桌面端默认加载的组合 baseline。
- 影响 `backend/scripts/ops/v2_backend_refactor_baseline_contract.json` 当前锚点。
- 不修改 stock/ETF runtime 代码逻辑；只是正式锚点切换。
