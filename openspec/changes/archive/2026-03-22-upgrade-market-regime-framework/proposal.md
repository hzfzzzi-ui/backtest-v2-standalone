## Why

当前主线的市场状态判断本质上仍是 `MA200 + 斜率` 的简化价格过滤器，适合做执行门控，但不足以充当可解释、可审计的成熟 regime 框架。现在前端阶段蒙版已经把这个问题暴露出来：分段对横盘、震荡、假启动和风险切换的刻画过于粗糙，研究口径与展示口径都缺少足够的结构信息。

## What Changes

- 用“仅使用当时可观测 trailing 数据”的成熟 regime 框架替换当前简化状态机草图，明确区分趋势、风险、广度、参与度四类输入与它们的角色边界。
- 把市场状态判断从“单一价格过滤器”升级为“多因子 regime engine + 持续性/滞后规则 + 置信度输出”的正式 contract。
- 保留当前 `BULL / TRANS_UP / TRANS_DOWN / BEAR` 与 `TREND_MAIN / TREND_LIGHT / NO_TRADE` 作为对外兼容状态名，但重新定义其生成依据、切换条件和持久化规则。
- 为市场状态输出增加最小审计协议，包括输入特征快照、状态置信度、切换原因、持续天数和状态分布统计，避免再次出现“图上看起来不准但无法解释”的情况。
- 为前端结果图和配置工作台补齐 regime 语义说明、图例和参数分层，使展示不再直接绑定到单一 MA200 逻辑。
- **BREAKING**: `ma200-market-state` 的 REQUIREMENTS 将不再把 `close vs MA200 + slope` 视为正式市场状态真相，而只保留为兼容 fallback/简化模式。

## Capabilities

### New Capabilities

- `market-regime-framework`: 定义正式市场状态框架的输入因子、状态机、置信度、持久化规则和审计输出合同。

### Modified Capabilities

- `ma200-market-state`: 从“正式四态市场状态定义”降级为兼容 fallback 模式，并允许被新的 regime framework 取代。
- `regime-router`: 改为消费新的 regime state / confidence / persistence 输出，而不是只消费简化的 `MA200 + slope` 分类。
- `market-state-chart-overlay`: 改为展示新 regime framework 的状态段、切换语义和图例，不再默认等同于 MA200 状态机。
- `regime-signal-ui`: 改为暴露 regime engine 的正式配置层级，包括趋势、风险、广度、参与度与 persistence 参数，而非只暴露简化均线参数。

## Impact

- 影响后端核心模块：
  - `backend/core/engine_vector/regime_router_precompute.py`
  - `backend/core/engine_vector/regime_router_signal_provider.py`
  - `backend/core/engine_vector/multi_alpha_signal_provider.py`
  - 相关 config/compiler 透传链
- 影响前端模块：
  - `frontend/app/results-workbench/components/ResultsChart.vue`
  - `frontend/assets/js/artifacts.js`
  - `frontend/assets/js/charts.js`
  - `frontend/assets/js/results-chart-nav-override.js`
- 影响研究与诊断产物：
  - `portfolio_daily.csv`
  - `run_meta.json`
  - 新增 regime 诊断/审计字段与统计表
- 影响 OpenSpec 合同：
  - 新增市场状态框架能力 spec
  - 修改当前 MA200 状态机、regime router、overlay、UI 相关 spec
