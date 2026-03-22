## Why

当前 `baseline_V10.2` 的主问题已经收敛：不是整套市场状态机需要重写，而是 `BULL / TREND_MAIN` 内部仍混入了一批会在牛市内部快速失败的 breakout。前面的市场过滤 A/B 证明，继续改 regime 容易漏掉早期 runner，泛化和解释都变差。

因此下一步最值得做的是一轮**最小、可解释、低自由度**的 A/B：只在 `BULL / TREND_MAIN` 中，对已有 breakout 候选加一层坏 breakout veto，验证是否能减少 `BULL` 内部失败交易，同时不明显伤害早期趋势 runner。

## What Changes

- 新增一个可选的 `bull_breakout_quality_veto` 能力，只对 `BULL / TREND_MAIN` 且 `alpha_source in {breakout, pullback_overlap}` 的新买入候选生效。
- veto 只使用现有预计算特征，首轮只允许两个粗阈值：
  - `residual_strength_score`
  - `breakout_margin_score`
- 为 veto 增加稳定 reason_code 与诊断计数器，确保结果可审计、可复现、可在 artifact 中核对。
- 新增一轮最小 A/B 研究脚本：
  - A = 当前 `baseline_V10.2`
  - B = `baseline_V10.2 + bull_breakout_quality_veto`
- 本轮不修改默认 baseline，不改 exit，不改股票池，不改主排序核。

## Capabilities

### New Capabilities
- `bull-breakout-quality-veto`: 为 `BULL / TREND_MAIN` 的 breakout 候选提供一个可选、低自由度、可解释的坏 breakout veto。

### Modified Capabilities
- `signal-provider-protocol`: 扩展稳定诊断输出，要求 bull breakout veto 的阻断次数、阻断原因和阈值信息能进入 `DaySignals.diagnostics`、`run_meta.json` 和结果计数器。

## Impact

- 影响模块：
  - `backend/core/config`
  - `backend/api/backtest_v2`
  - `backend/core/engine_vector`
  - `backend/core/stage_pipeline/adapters`
  - `tests/unit`
  - `backend/scripts/ops`
- 不影响：
  - `40日突破 + 40日个股残差动量排序` 主排序核
  - 默认 `baseline_V10.2`
  - exit 逻辑
  - 股票池 / 数据角色 / PIT 模式
