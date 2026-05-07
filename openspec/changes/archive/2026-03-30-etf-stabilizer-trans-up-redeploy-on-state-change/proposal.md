## Why

当前正式 ETF stabilizer 在 `TRANS_UP` 状态下几乎不承接恢复期仓位，导致大量正目标预算停留在纸面上，没有转成实际暴露。最新 ETF 子实验显示 `TRANS_UP` 有 210 个交易日，但只发生了 1 次 `BUY`，这已经足够说明“只等月末 rebalance”会错过恢复期。

## What Changes

- 允许 formal ETF stabilizer 在状态从更防守阶段切换到 `TRANS_UP` 时，触发一次不等待月末的 `strategic floor` redeploy。
- redeploy 仅针对 `core_accumulator`，不触发 `tactical_satellite` 轮换，不把非月末日升级成完整 rebalance。
- redeploy 继续服从 Governor 硬阻断、next-open 执行、现有 lot/cash 约束，不绕过预算真相。
- 增加最小可审计输出，明确区分“月末常规 rebalance”与“TRANS_UP 状态切换 redeploy”。

## Capabilities

### New Capabilities
- 无

### Modified Capabilities
- `cn-etf-beta-sleeve`: formal ETF stabilizer 需要在 `TRANS_UP` 状态切换时支持一次 core-only 的 strategic floor redeploy，并输出可审计证据。

## Impact

- 受影响模块：
  - `backend/core/engine_vector/cn_etf_beta_signal_provider.py`
  - `backend/core/config/etf_beta_contract.py`
  - `backend/core/stage_pipeline/adapters/daily_accounting.py`
  - `tests/unit/test_cn_etf_beta_signal_provider.py`
  - `tests/unit/test_bridge_adapter_accounting.py`
- 受影响产物：
  - `orders.csv`
  - `portfolio_daily.csv`
  - `audit.json` / `run_meta.json` 中的 ETF 归因证据
- 不在本次范围：
  - 不改 ETF 池
  - 不改 RS 窗口
  - 不改 `controlled_accumulation` 总语义
  - 不把 monthly rebalance 改成更高频主逻辑
