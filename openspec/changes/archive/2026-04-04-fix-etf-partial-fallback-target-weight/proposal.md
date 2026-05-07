## Why

当前 ETF standalone research mainline 在 partial fallback fill 场景下，会把原始目标权重为 `0` 的 fallback 标的压成与核心标的等权的 `target_weight`。这会把 fallback 买单伪装成接近半仓的绝对目标金额，直接制造 `SKIP_NO_CASH`，并污染 ETF 单腿的真实 deployability 判断。

## What Changes

- 修正 ETF research mainline 的 partial fallback fill 压缩逻辑，只在原始正目标权重标的之间压缩 live target。
- 保留 full fallback replacement 的既有能力；当选中集合里不存在任何原始正目标权重时，fallback 仍可承接 live target。
- 增加针对 partial fill 与 full replacement 两种场景的回归测试，并重跑 ETF 单腿长窗确认 `SKIP_NO_CASH` 与目标金额结构变化。

## Capabilities

### New Capabilities

- 无

### Modified Capabilities

- `cn-etf-beta-sleeve`: 收紧 ETF partial fallback fill 的目标仓位合同，禁止零原始目标的 fallback 标的在 partial fill 下获得等权正 `target_weight`。

## Impact

- 影响代码：
  - `backend/core/engine_vector/etf_beta/selection.py`
  - `tests/unit/test_cn_etf_beta_signal_provider.py`
- 不改动：
  - `signal_postprocess.py`
  - execution kernel
  - ETF 绝对过滤器 / growth slot / benchmark gate
