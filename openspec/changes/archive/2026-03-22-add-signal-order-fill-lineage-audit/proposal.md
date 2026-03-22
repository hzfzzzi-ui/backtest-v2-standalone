## Why

当前正式主线只能在天级看到 `days_with_fills`、`days_with_scheduled_orders` 和成交结果，无法把某条信号如何变成订单、何时被排到下一交易日、最终是否成交或丢失，作为正式审计真相表达出来。没有稳定的 `signal -> order -> fill` lineage，就无法可靠审同日成交、错日成交、漏排单、漏成交和 reason_code 漂移。

这不仅影响交易细节追责，也限制了 `timing_alignment` 从“合同推断”升级为“证据驱动”的正式门禁。现在单独立 change，是为了把链路 id、生命周期台账和审计摘要作为独立能力推进，不和会计恒等式审计耦合在同一次改动里。

## What Changes

- 为当前正式执行链引入稳定的 lineage id 合同，覆盖 `signal_id`、`order_id`、`fill_id` 及其父子关系。
- 新增单级生命周期台账产物，记录信号生成、订单排程、提交、成交、拒绝、取消或失效等关键状态流转。
- 扩展 `audit.json` 与 `research_audit`，使正式审计可以引用 lineage 台账，对 dropped order、same-day fill、schedule drift 和 missing fill 给出可复核结论。
- 明确摘要与明细分层：`audit.json` 只放统计、样本与引用，不内联全量台账，避免主审计产物膨胀。

## Capabilities

### New Capabilities
- `execution-lineage-ledger`: 定义 `signal -> order -> fill` 稳定 id、生命周期状态流转、台账产物和查询摘要契约。

### Modified Capabilities
- `backtest-audit`: 变更正式 execution audit 要求，使其必须输出 lineage 摘要、异常样本和明细引用，而不再只提供天级成交计数。
- `backtest-research-audit`: 变更研究审计对时间与执行链证据的要求，使 `timing_alignment` 或等价 gate 能基于真实 lineage 证据而不仅是配置推断。
- `execution-contract-goldens`: 变更执行链 contract 要求，明确 signal/order/fill 之间必须通过显式稳定 id 交接并可被 golden 校验。

## Impact

- 影响信号生成、订单规划、fill accounting、artifact finalization 与 experiment surface。
- 可能新增 `ledger` 类 artifact，并影响 `audit.json`、`run_meta.json` 和 machine output 引用。
- 需要补充跨阶段合同测试、golden 测试与审计契约测试，覆盖 same-day fill、漏排单、漏成交、取消/拒绝和 reason_code 追溯。
