## Why

当前 V10.1 结果工作台中的交易漏斗存在大量 `0` 值，但问题并不单纯来自前端展示。

已核查到两类失真同时存在：

- 一部分阶段在后端本来就是“未单独计数 / unavailable”，例如 `buy_stage_funnel` 中的某些阶段使用 `available=false` 且计数为 `null`；但前端在结果格式化时将 `null` 直接收敛为 `0`，把“没有独立计数”伪装成了“真实为 0”。
- 另一部分阶段的计数确实在 V10.1 stage pipeline 中被压平了。`daily_accounting` 会把多个阶段回退成相同的 `len(day_signals.buy_signals)` 或 `selected_symbols`，而多个 signal provider 也没有稳定输出前后阶段的真实 diagnostics，导致漏斗出现大面积平直或缺口。

仓库主 specs 中已经存在 `daily-funnel-schema`，归档变更 `daily-row-normalize` 也曾正式定义过 daily_row 的买卖漏斗字段。这说明当前问题更像是合同在 V10.1 runtime / workbench 组合下发生了漂移，而不是一个全新的需求。

由于该问题同时涉及：

- `stage pipeline` 诊断合同
- `stage_funnel` surface 语义
- 结果工作台对 unavailable/null 的展示语义

它不适合被当作纯前端修饰项处理，必须先在 OpenSpec 中重新收紧边界。

## What Changes

- 收紧 `daily-funnel-schema`，明确 V10.1 买入漏斗相关字段必须满足以下二选一语义：
  - 提供真实阶段计数
  - 明确标记为 `available=false` 且对应计数为 `null`
- 明确 stage pipeline 的漏斗计数 owner：后端 MUST 从 provider diagnostics、`debug_plan`、daily_row 等正式诊断来源投影阶段计数；前端 MUST NOT 倒推、补造或把缺失阶段伪装成真实 `0`。
- 明确 `stage_funnel` surface 的 unavailable/null 语义，要求结果工作台在渲染时保留“未单独计数”的状态，并与“真实为 0”区分展示。
- 明确本轮修复只允许改变诊断采集与展示口径，不允许改变执行时点、成交规则、仓位构建、NAV、交易笔数、benchmark 或 baseline_V10.1 的研究口径。
- 为验证面增加约束：修复前后必须同时对比 `portfolio_daily.csv`、`run_meta.counters.buy_stage_funnel`、结果工作台漏斗视图，并确认收益与交易结果无漂移。

## Capabilities

### Modified Capabilities

- `daily-funnel-schema`: 补充 unavailable/null 语义、真实阶段计数来源约束，以及 V10.1 stage pipeline 不得用回退值压平多个阶段的要求。
- `results-workbench-finalization`: 补充交易漏斗展示约束，结果工作台必须区分“未单独计数”与“真实为 0”，不得把 `available=false` 或 `null` 计数渲染成 0。
- `experiment-artifact-service`: 补充 `stage_funnel` 子面的语义约束，artifact/service 层输出的阶段可用性信息必须原样保留到前端消费面。

## Impact

- 影响代码：
  - `backend/core/stage_pipeline/adapters/daily_accounting.py`
  - `backend/core/engine_vector/*signal_provider*.py`
  - `backend/api/backtest_v2/artifacts_impl.py`
  - `frontend/app/results-workbench/helpers/stageFunnelFormatting.js`
  - `frontend/assets/js/artifacts.js`
- 影响边界：
  - V10.1 stage diagnostics 的 owner 和字段语义
  - `stage_funnel` lazy section 的 surface 语义
  - 结果工作台对 unavailable/missing/zero 的展示规则
- 不影响的内容：
  - baseline_V10.1 的执行时点、成交规则、风险预算、benchmark、研究主逻辑
  - 正式交易结果、NAV 曲线和收益统计口径
- 风险边界：
  - 这是 L3 级合同收紧，接近回测主链，但目标仅限“诊断真实化 + 展示纠偏”；
  - 若修复导致交易结果变化，应直接判定为越界，而不是视作附带优化。
