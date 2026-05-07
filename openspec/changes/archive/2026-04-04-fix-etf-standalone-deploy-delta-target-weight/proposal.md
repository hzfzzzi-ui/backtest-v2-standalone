## Why

当前 ETF standalone inter-rebalance deploy 会把 `target_weight` 写成“最终目标仓位”，而不是“本次应补的增量仓位”。在组合已经持有防守仓位或其他 ETF 暴露时，这会把 core 宽基买单放大成接近整仓的绝对目标金额，直接制造大量 `SKIP_NO_CASH`，并扭曲 `BULL` 下的真实 deployability。

## What Changes

- 修正 ETF standalone inter-rebalance deploy 的 `target_weight` 语义，使 emitted BUY signal 表达“应补的 delta notional”。
- 保持 monthly rebalance 与 formal `TRANS_UP redeploy` 的既有语义不变，仅收口 standalone inter-rebalance deploy。
- 增加针对 `BULL` 下已有防守仓位时的 delta sizing 回归测试，并重跑 ETF 单腿长窗核对 `BULL` 暴露与绩效变化。

## Capabilities

### New Capabilities

- 无

### Modified Capabilities

- `cn-etf-beta-sleeve`: 调整 ETF standalone inter-rebalance deploy 的买单目标仓位合同，要求其使用增量 deploy gap 而不是最终整仓目标。

## Impact

- 影响代码：
  - `backend/core/engine_vector/etf_beta/execution_paths.py`
  - `tests/unit/test_cn_etf_beta_signal_provider.py`
- 不改动：
  - `selection.py` 的 partial fallback fix
  - benchmark gate
  - formal `TRANS_UP redeploy`
  - execution kernel 通用现金/lot/slot 逻辑
