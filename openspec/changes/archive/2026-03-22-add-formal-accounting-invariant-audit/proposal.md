## Why

当前正式主线里的 `audit.json` 已能稳定输出 `stage_pipeline` 摘要和 `research_audit` 五个 gate，但缺少对现金守恒、持仓守恒、NAV 守恒、负现金和超仓上限的正式审计。仓库里虽然保留了旧的 `AuditCollector` 思路，但它没有成为当前 stage pipeline 主线的唯一真相，导致“交易审计最基础的会计恒等式”没有被当前正式产物可靠承接。

这会直接削弱审计可信度：即使 `execution_realism` 和 `timing_alignment` 通过，只要主线没有把记账约束显式写入正式审计，就仍然无法证明回测执行结果在资金和持仓层面自洽。现在单独立 change，是为了先补最小但关键的主线审计空白，不把它和更大的订单生命周期改造绑在一起。

## What Changes

- 为当前 stage pipeline / foundation shell 主线新增正式的 `accounting_integrity` 审计能力，使用 canonical accounting snapshot 或等价正式快照生成主线审计证据。
- 扩展 `audit.json` 的 execution audit 部分，补齐现金守恒、持仓守恒、NAV 守恒、负现金、超仓上限的汇总指标、样本和异常标记。
- 扩展 `research_audit`，让研究门禁能够基于主线会计恒等式证据给出 `PASS/WARN/FAIL/UNKNOWN` 结论，而不是仅依赖市场现实性和时间合同。
- 保持现有 `stage_summary`、`stage_pipeline`、`research_audit` 和旧产物引用兼容，不引入第二份并行审计真相文件。

## Capabilities

### New Capabilities
- `accounting-integrity-audit`: 定义主线正式会计恒等式审计的输入、输出、证据摘要和失败样本约定。

### Modified Capabilities
- `backtest-audit`: 变更 `audit.json` 要求，使当前正式 execution audit 必须承接会计恒等式审计，而不是只保留 stage 摘要和旧兼容字段。
- `backtest-research-audit`: 变更 `research_audit` gate 集合与聚合口径，新增基于主线会计恒等式证据的 `accounting_integrity` 判定。

## Impact

- 影响 `backend/core/stage_pipeline`、`backend/core/engine_runtime/foundation_shell.py`、`backend/core/audit/research_audit.py` 和 `backend/api/backtest_v2/artifacts_finalize.py`。
- 影响 `audit.json` / `machine/audit.json` 契约，以及相关 experiment surface 的审计字段。
- 需要补充单元测试与集成测试，覆盖主线记账守恒、异常标记、研究门禁聚合和兼容性。
