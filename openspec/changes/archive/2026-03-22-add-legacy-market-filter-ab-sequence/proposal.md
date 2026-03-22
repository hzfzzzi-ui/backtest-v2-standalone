# Proposal

## Why

当前 `baseline_V10.2` 主线的问题，已经从“市场状态机整体是否替换”收敛成一个更具体的问题：

- `TRANS_UP` 阶段的开闸可能过宽
- `TRANS_UP / TRANS_DOWN` 阶段的去风险可能过慢

前面的实验已经证明，直接把 `weekly_five_state` 或其 veto 规则迁到主线并不成立。下一步最值得做的，不是继续更换整套状态机，而是对当前更可信的 `ma200_legacy` 做一组**最小、可回退、可归因**的 A/B 序列实验。

## What Changes

本 change 只做三组按顺序推进的最小 A/B：

1. **AB1**：拆分 `TRANS_UP / TRANS_DOWN` 的执行预算倍数
   - 保持 `ma200_legacy` 状态定义不变
   - 只允许 `TRANS_UP` 与 `TRANS_DOWN` 使用不同 multiplier
2. **AB2**：在 AB1 基础上，禁止 `TRANS_UP` 新开仓
   - 允许已有持仓继续走退出链
   - 不改变 `TRANS_UP` 的状态标签
3. **AB3**：在 AB2 基础上，将 legacy 长均线窗口从 `200 -> 160`
   - 不直接跳到 `120`
   - 验证是否有必要让大方向判定略微提速

## Capabilities

### New Capabilities

- `legacy-market-filter-ab`: 为 `ma200_legacy` 提供最小 A/B 序列研究能力，按顺序比较 AB1 / AB2 / AB3。

### Modified Capabilities

- `ma200-market-state`: legacy 市场过滤配置新增 `long_ma_window`、`trans_up_multiplier`、`trans_down_multiplier`、`freeze_trans_up_entries`，并允许 MA 长窗从固定 200 改为可配置。
- `regime-router`: 当 `ma200_legacy` 启用 `freeze_trans_up_entries` 时，`TRANS_UP` 阶段不得产生新的买入信号，但已有持仓退出行为保持不变。

## Impact

- 影响模块：
  - `backend/core/config`
  - `backend/api/backtest_v2`
  - `backend/core/engine_vector`
  - `backend/core/stage_pipeline/adapters`
  - `tests/unit`
  - `backend/scripts/ops`
- 不影响：
  - 个股信号逻辑（`40日突破 + 40日个股残差动量排序`）
  - 股票池 / 数据角色 / PIT 模式
  - 退出规则
  - `ma200_legacy` 默认主线配置
