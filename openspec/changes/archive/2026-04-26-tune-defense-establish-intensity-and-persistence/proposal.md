## Why

当前 `risk_on -> defensive` 的 `sell-first + defense establish` 已经真实落到订单层，但最新版本相对 `sell-first-only` 出现了收益与 Calmar 回落。问题已经不在结构层，而在 `defense establish` 的建仓强度与持仓延续是否过强。

## What Changes

- 为共享账户 transition execution 增加 `defense establish` 研究参数，不再继续改结构层 owner。
- 把 `defense establish` 的触发边界限定、已持仓 top-up 许可做成正式政策字段。
- 以固定结构、固定 owner 的前提，运行 A/B 对比，选择更合适的防守建仓版本作为下一步研究默认值。

## Capabilities

### New Capabilities
- `defense-establish-research-tuning`: 定义 `defense establish` 的研究参数与 A/B 变体约束。

### Modified Capabilities
- `account-transition-defense-establish`: 防守建仓从固定行为改为受研究参数控制。
- `shared-account-transition-execution-runtime`: 共享执行 runtime 必须输出当前生效的防守建仓研究变体。

## Impact

- backend/core/services/account_allocator_shadow.py
- backend/core/engine_vector/etf_beta/selection.py
- backend/core/engine_vector/etf_beta/execution_paths.py
- outputs/experiments/* 研究产物对比
- openspec/specs 与 change artifacts
