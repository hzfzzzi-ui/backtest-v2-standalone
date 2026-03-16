## 1. 候选审计字段补齐

- [x] 1.1 在 `backend/core/portfolio/portfolio_runtime.py` 为候选审计行补充资金拦截所需字段：`cash_available`、`estimated_qty`、`estimated_amount`、`estimated_price`、`cash_blocked_flag`、`cash_blocked_reason`；DoD：明确的 `SKIP_NO_CASH` 行会带齐这些字段，其他候选行字段为空或默认值；验证：新增/更新单测；风险：误改执行行为。

## 2. Recent cash-blocked artifact

- [x] 2.1 在 `backend/api/backtest_v2/protocol.py` 注册 canonical artifact `cash_blocked_buys_recent.csv`；DoD：protocol 常量包含新 key；验证：protocol 单测；风险：artifact key 命名与现有 surface 不一致。
- [x] 2.2 在 `backend/api/backtest_v2/artifacts_diagnostics.py` 新增 recent cash-blocked builder，并在 `backend/api/backtest_v2/artifacts_finalize.py` 接入 finalize pipeline；DoD：每个实验目录稳定生成 `cash_blocked_buys_recent.csv`，只包含最近 5 个交易日的资金不足拦截明细；验证：artifact 单测；风险：日期窗口选取错误。

## 3. Surface 暴露与验证

- [x] 3.1 在 `backend/core/services/experiment_query_service.py` 暴露 `cash_blocked_buys_recent` surface section；DoD：`surface` lazy section 和 `surface/{section}` 都能读取新 artifact；验证：query service 单测；风险：section 命名与 artifact key 脱节。
- [x] 3.2 运行定向测试并确认 `V10.1` 锚点行为未变；DoD：相关 pytest 通过，且本 change 不引入收益/交易数口径漂移说明；验证：pytest / compile；风险：诊断字段变更意外影响候选产物下游。
