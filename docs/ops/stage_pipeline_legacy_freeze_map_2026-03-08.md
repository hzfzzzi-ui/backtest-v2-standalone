# Stage Pipeline Legacy Freeze Map (2026-03-08)

## 结论

从 `v2-single-path-9stage-engine` 的 3.x 起，公开单次回测主链已经固定为：

`config_json -> compiler -> DataBundle -> foundation shell -> stage pipeline shell -> legacy adapter -> legacy execution kernel`

这意味着：

- `stage pipeline shell` 是唯一允许继续演进的公开编排壳
- `legacy adapter` 只允许做输入映射和兼容包裹，不允许新增公开入口
- 更老的 orchestrator / multi-route shell 进入冻结状态，不再接受新功能

## 当前职责分层

### 1. 公开主链，允许继续演进

- `backend/core/tools/experiment_runner.py`
  - 职责：公开单次回测编排入口
  - 当前状态：已通过 `foundation_shell` 进入 stage pipeline
  - 规则：允许继续做公开主链收敛，但不得绕回旧 public orchestrator

- `backend/core/engine_compat/foundation_shell.py`
  - 职责：公开兼容壳
  - 当前状态：已降级为把请求参数编译成 `LegacyStagePipelineRequest`，再委托给 stage pipeline
  - 规则：允许继续瘦身；不允许重新长出第二条公开执行路径

- `backend/core/stage_pipeline/`
  - 职责：唯一日循环 stage 总线、时点边界、collector、adapter
  - 当前状态：当前 change 的目标实现层
  - 规则：允许继续扩展

### 2. 保留为执行核，暂不删除

- `backend/core/stage_pipeline/adapters/legacy_adapter.py`
  - 职责：把 stage shell 接到旧 provider / order planner / fill / metrics 核上
  - 当前状态：过渡层
  - 规则：只允许做等价映射、审计补充和拆分准备，不允许加新的公开配置真相

- `backend/core/engine_vector/breakout_signal_provider.py`
- `backend/core/engine_vector/generic_signal_provider.py`
- `backend/core/engine_vector/regime_router_signal_provider.py`
- `backend/core/engine_vector/sma_signal_provider.py`
- `backend/core/engine_vector/data_matrix.py`
- `backend/core/engine_vector/features.py`
- `backend/core/engine_vector/signal_matrix.py`
- `backend/core/engine_vector/candidate_index.py`
- `backend/core/portfolio/portfolio_builder.py`
  - 职责：旧计算核、下单规划、fill/NAV/metrics 会计核
  - 当前状态：仍被 stage adapter 复用
  - 规则：视为 execution kernel；允许抽纯计算，不允许新增 public routing

### 3. 公开编排冻结，不再扩展

- `backend/core/portfolio/portfolio_builder.py`
  - 冻结范围：旧 `run_portfolio_backtest()` 作为公开编排入口的语义
  - 说明：它可以继续作为 adapter 复用的 kernel，但不再承担未来主线 orchestrator 职责

- `backend/core/tools/experiment_runner.py` 中任何直接连到旧 orchestrator 的新分支
  - 说明：禁止新增 “如果 X 就走旧 strict / 如果 Y 就走另一条壳” 的逻辑

- `backend/core/engine_vector/portfolio_simulator_strict.py` 中对外可见的多路由语义
  - 说明：旧 runtime route 仍可能在内部存在，但只能通过 stage adapter 被复用

## 当前 route 映射

### 仍被 stage adapter 使用的 legacy route

- `provider_breakout_runtime`
  - 来源：`BreakoutTrendStrategy -> BreakoutTrendProvider`
  - 状态：保留

- `generic_inline_runtime`
  - 来源：`CompositeStrategy -> GenericSignalProvider`
  - 状态：保留

- `regime_router_inline_runtime`
  - 来源：`RegimeRouter -> RegimeRouterSignalProvider`
  - 状态：保留

- `strict_inline_runtime`
  - 来源：其余 strict MA 类策略 -> `SMASignalProvider`
  - 状态：保留

### 已冻结的旧公开路由能力

- 旧的 “直接 public shell -> run_portfolio_backtest()” 语义
- 旧的 “不同 stage 开关切换不同执行壳” 语义
- 旧的 “新增 artifact 兼容补丁但不走 stage pipeline” 语义

## 变更准入规则

后续若修改以下文件，必须同时满足：

- `python backend/scripts/baseline_regression_check.py --rerun --write-to-candidate` 通过
- `exp_20260308_021045840_cde0` 的 `portfolio_daily.csv`、`portfolio_trades.csv`、`portfolio_candidates.csv`、`perf.json`、`config_truth` 保持 `PASS`
- 若出现 `WARN`，只能来自 `diagnostic_drift`，当前已知仅 `report.html`

## 下一批允许做的事

- 把更多 legacy decision logic 继续内收进 `stage_pipeline/adapters/`
- 逐步减少 `foundation_shell.py` 中除委托外的逻辑
- 在不破坏基线的前提下，把 `legacy_adapter.py` 内部再拆成更清晰的候选流/持仓流模块

## 明确禁止

- 在 `foundation_shell.py` 重新加一条并行公开执行路径
- 在 `experiment_runner.py` 新增绕过 stage pipeline 的特例分支
- 为了方便试验，直接改旧 execution kernel 的交易口径而不先过基线门禁
