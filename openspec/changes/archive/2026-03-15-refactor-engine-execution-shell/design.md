## Context

当前回测执行内核至少存在三层执行壳并行：

- [portfolio_builder.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/portfolio/portfolio_builder.py) 中的 `run_portfolio_backtest`，仍承载价格索引、NAV、订单生成和完整回测循环。
- [portfolio_simulator_strict.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/engine_vector/portfolio_simulator_strict.py) 中的 `run_vector_portfolio_backtest_strict`，又承载 route 分发、多因子门控、breakout 分支和 generic 分支。
- [foundation_shell.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/engine_compat/foundation_shell.py) 与 [shell.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/stage_pipeline/shell.py) 已经开始承担兼容壳和 stage pipeline，但还没有成为唯一正式执行入口。

此外，`stage_pipeline` 已经具备自然的职责切面：

- `route_runtime.py`
- `runtime_state.py`
- `day_controls.py`
- `candidate_flow.py`
- `holding_flow.py`
- `signal_postprocess.py`
- `order_planning.py`
- `fill_accounting.py`
- `daily_accounting.py`
- `result_bridge.py`

这说明新的执行壳骨架已经存在，但旧执行壳还没有退场。继续双轨并行会导致：

1. 相同研究口径在不同入口间出现静默漂移。
2. 新实验逻辑不知道该挂在哪一层，最终又堆回巨型主循环。
3. AI 自动生成实验脚本时容易绕过统一执行总线，直接写入新的特判分支。

## Goals

- 明确 `stage_pipeline` 是唯一正式执行总线。
- 把信号生成、候选筛选、排序、门控、订单规划、成交记账、日终会计和结果桥接拆成稳定边界。
- 把 [portfolio_simulator_strict.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/engine_vector/portfolio_simulator_strict.py) 和旧 [portfolio_builder.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/portfolio/portfolio_builder.py) 主循环降级为过渡 shim/legacy layer。
- 为后续所有新实验建立 `bus-first` 约束：新逻辑必须先接执行总线，再能被脚本或 study 调用。
- 在不改变研究口径的前提下，为执行壳建立可回归、可审计、可迁移的结构。

## Non-Goals

- 本 change 不调整 baseline 默认参数。
- 本 change 不修改信号公式本身，不重写 `*_signal_provider.py` 的 alpha 计算。
- 本 change 不修改 benchmark、手续费、滑点、股票池、调仓频率和执行时点。
- 本 change 不做大规模性能优化，除非为了保证结构迁移必须引入轻量缓存。
- 本 change 不尝试构建通用 DAG 引擎或插件平台，第一版只覆盖当前最高频的执行模块类型。

## Research Invariants

以下约束在整个迁移中不可被改变：

- 使用 `t` 日收盘后信息生成信号，默认 `t+1` 执行。
- 停牌、涨跌停、无成交、缺 bar 都不能被理想化成交。
- 行业、指数成分、财务、宽度和市场状态数据必须维持历史可得口径。
- 日频价格索引、NAV、trade rows、metrics 计算口径必须保持可比。

额外红线：

- AGENTS.md `10.1 价格型信号` 口径不能出现任何结果偏移。
- 结构可以重构，但价格型信号的时点与执行口径绝不允许出现任何结果偏移。

这意味着：

- 结构可改，研究语义不可暗改。
- 主循环可外提，成交规则和对齐规则不可顺手“优化”。

## Design Principles

### 原则 1：Signal、Plan、Fill、Accounting 分层

执行壳以后必须按这四类角色分层：

- `Signal`
  - provider 负责在当前已知信息下给出候选、持仓动作和退出信号。
- `Plan`
  - order planner 负责把信号翻译成次日订单意图。
- `Fill`
  - fill accounting 负责按成交假设执行订单。
- `Accounting`
  - daily accounting 负责日终仓位、现金、NAV 和 audit rows。

### 原则 2：Provider 不直接记账

- `*_signal_provider.py` 只输出 `precompute + day_signals`。
- provider 不得直接改现金、仓位和 NAV。
- provider 不得直接写 trade rows。

### 原则 3：执行总线优先于 route 特判

- 新逻辑优先挂到 `stage_pipeline` 的 built-in modules 或 provider，不再往 strict/legacy 主流程堆分支。
- route 只负责选择 provider 或模块组合，不再决定整段执行流程。

### 原则 4：结果不漂移高于结构漂亮

- 第一优先级不是“代码变漂亮”，而是“同口径回放结果完全不漂移”。
- 任何改动只要让 `orders / trades / NAV / perf / counters` 产生非预期偏移，就视为失败。

### 原则 5：Legacy 是待删除 shim，不是长期层

- legacy 只允许作为短期过渡 shim 存在。
- 新逻辑一律禁止进入 legacy。
- 一旦 goldens 在最小覆盖集上稳定通过，就进入删除阶段。

## Target Execution Architecture

```text
RuntimePlan
  -> foundation_shell
  -> stage_pipeline.shell
       -> route_runtime
       -> runtime_state
       -> day_controls
       -> candidate_flow
       -> holding_flow
       -> signal_postprocess
       -> order_planning
       -> fill_accounting
       -> daily_accounting
       -> collector
       -> result_bridge
  -> PortfolioBacktestResult
```

未来的新实验逻辑只允许从两条路径进入：

```text
1. provider path
   engine_vector/<provider>.py
   -> route_registry

2. pipeline built-in module path
   stage_pipeline/builtins/<kind>/<module>.py
   -> registry / resolver
```

额外纪律：

- 一轮实验的主改动原则上只允许动其中一层。
- 同轮同时改两层，只允许是接线型变更，不允许是双重策略改动。

## Directory and File Responsibilities

目标目录：

```text
backend/core/
  engine_compat/
    foundation_shell.py
  stage_pipeline/
    shell.py
    context.py
    contracts.py
    collector.py
    registry.py
    resolver.py
    builtins/
      candidate_filters/
      rankers/
      gates/
      exits/
      sizers/
      reporters/
    adapters/
      route_runtime.py
      runtime_state.py
      day_controls.py
      candidate_flow.py
      holding_flow.py
      signal_postprocess.py
      order_planning.py
      fill_accounting.py
      daily_accounting.py
      result_bridge.py
      stage_applicability.py
      legacy_adapter.py
  portfolio/
    types.py
    price_index.py
    nav_snapshot.py
    metrics.py
    selection_order.py
    legacy_loop.py
  engine_vector/
    signal_provider.py
    route_registry.py
    data_matrix.py
    signal_matrix.py
    features.py
    breadth.py
    audit_collector.py
    breakout_signal_provider.py
    generic_signal_provider.py
    multi_alpha_signal_provider.py
    regime_router_signal_provider.py
    sma_signal_provider.py
    portfolio_simulator_strict.py
```

职责定义：

- `foundation_shell.py`
  - 主系统到执行总线的唯一兼容门。
  - runtime service 最终只能调用它，不直接调用 strict/legacy 壳。
- `stage_pipeline/shell.py`
  - 唯一正式日循环壳。
  - 决定阶段顺序，不决定策略公式。
- `stage_pipeline/context.py`
  - 定义 `DayContext`、`PortfolioState`、`DataBundleView` 等只读/受控状态。
- `stage_pipeline/contracts.py`
  - 定义 `StageInputs`、`StageOutputs`、`ExecutionIntent`、`PipelineResult`。
- `stage_pipeline/collector.py`
  - 收集阶段统计和审计数据。
- `stage_pipeline/registry.py`
  - 模块注册表。
  - 新的 built-in module 必须先在这里注册。
- `stage_pipeline/resolver.py`
  - 按 config/study 解析并组装 module set。
- `stage_pipeline/builtins/*`
  - 执行总线可插拔模块集合。
  - 第一版只正式支持：
    - `candidate_filters`
    - `rankers`
    - `gates`
    - `exits`
    - `sizers`
    - `reporters`
- `stage_pipeline/adapters/order_planning.py`
  - 统一次日订单规划。
  - 是正式 contract 边界的一部分。
- `stage_pipeline/adapters/fill_accounting.py`
  - 开盘成交和资金/仓位更新。
  - 是正式 contract 边界的一部分。
- `stage_pipeline/adapters/daily_accounting.py`
  - 日终估值、NAV、daily rows、turnover。
  - 是正式 contract 边界的一部分。
- `stage_pipeline/adapters/result_bridge.py`
  - 组装 `PortfolioBacktestResult`。
- `stage_pipeline/adapters/legacy_adapter.py`
  - 迁移期兼容层。
  - 冻结，不再接收新逻辑。
  - golden 稳定后进入删除阶段。
- `portfolio/types.py`
  - `PortfolioOrder`、`PortfolioBacktestResult` 等纯类型定义。
- `portfolio/price_index.py`
  - 开盘/收盘索引构建。
- `portfolio/nav_snapshot.py`
  - NAV 快照计算。
- `portfolio/metrics.py`
  - 绩效指标计算。
- `portfolio/selection_order.py`
  - 纯排序和选择辅助函数。
- `portfolio/legacy_loop.py`
  - 旧 `run_portfolio_backtest` 的冻结版本，只承担过渡职责。
- `engine_vector/signal_provider.py`
  - provider 协议和共享退出规则。
- `engine_vector/route_registry.py`
  - 正式 `strategy -> provider` 映射层。
- `engine_vector/portfolio_simulator_strict.py`
  - 迁移期间作为薄 shim。
  - golden 稳定后删除。

## Bus-First Extension Model

后续 AI 新实验和人工扩展都必须遵循这条固定纪律：

```text
新增/修改逻辑
  -> provider or pipeline built-in module
  -> registry / route_registry / resolver
  -> runtime config or study chooses it
  -> foundation_shell
  -> stage_pipeline
```

### 路径 A：新增 provider

适用于：

- 真正新增一类信号生成机制。
- 新的 route。
- 新的 `precompute + day_signals` 组合。

接入步骤：

1. 在 `engine_vector/` 新增 provider。
2. 在 `route_registry.py` 注册 route。
3. 在 runtime plan/config 中暴露 route 选择。
4. 让 `foundation_shell` 和 `stage_pipeline` 消费统一 provider 协议。

### 路径 B：新增 pipeline built-in module

适用于：

- candidate filter
- ranker
- gate
- exit adapter
- sizer
- reporter

接入步骤：

1. 在 `stage_pipeline/builtins/<kind>/` 增加模块。
2. 在 `registry.py` 注册。
3. 在 `resolver.py` 里允许 config/study 选择。
4. 通过 study 或 runtime config 组合启用。

### 禁止路径

- 不允许再往 [portfolio_simulator_strict.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/engine_vector/portfolio_simulator_strict.py) 主函数里堆新分支。
- 不允许再往 [portfolio_builder.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/portfolio/portfolio_builder.py) 主流程里堆新逻辑。
- 不允许在脚本层直接注入新的成交或记账逻辑。
- 不允许把研究特判写进 `legacy_adapter.py` 或 `legacy_loop.py`。

## Execution Contracts

建议建立以下执行契约。

### Contract 1: `RuntimePlan`

最小字段：

- `strategy_route`
- `provider_ref`
- `data_bundle_refs`
- `execution_assumptions`
- `risk_controls`
- `pipeline_modules`

### Contract 2: `ExecutionIntent`

用于把信号输出和下游订单规划解耦。

最小字段：

- `as_of_date`
- `buy_candidates`
- `sell_candidates`
- `hold_overrides`
- `risk_flags`
- `ranking_payload`

### Contract 3: `AccountingSnapshot`

用于统一 fill 和 daily accounting 间的状态交接。

最小字段：

- `cash`
- `positions`
- `filled_orders`
- `trade_rows`
- `daily_marks`
- `counters`

### Contract Discipline

- `order_planning`、`fill_accounting`、`daily_accounting` 是正式 contract 边界。
- 后续执行逻辑不得靠隐式 dict 字段在这三段之间传递核心状态。
- `reporters` 只采集机器读诊断和审计信息，不得影响交易决策。

## Migration Strategy

### 阶段 0：补齐 goldens

在主循环正式替换前，必须先补这组最小覆盖集：

- `baseline_V10`
- 一个 locked candidate preset
- 一个 representative generic route
- 一个 representative breakout route

每组至少覆盖：

- `orders`
- `trades`
- `NAV`
- `perf`
- `counters`

没有这组 golden，不进入主循环替换。

### 阶段 1：正式化 `route_registry`

- 把 strict 壳中的 route 判断提取到 `route_registry.py`。
- 先保持 provider 行为不变。

### 阶段 2：完善 `stage_pipeline` 合同

- 把 `DayContext`、`ExecutionIntent`、`AccountingSnapshot` 固化为稳定契约。
- 保证 `order_planning / fill_accounting / daily_accounting` 的输入输出不再靠隐式 dict 约定。

### 阶段 3：让 strict 壳转调 pipeline

- `run_vector_portfolio_backtest_strict` 不再自己承载主要流程。
- 改为：
  - 解析 route
  - 组装 runtime plan
  - 调 `foundation_shell`
  - 返回统一结果

### 阶段 4：收缩 `portfolio_builder.py`

- 把纯函数外提到：
  - `price_index.py`
  - `nav_snapshot.py`
  - `metrics.py`
  - `selection_order.py`
- 把老主循环沉到 `legacy_loop.py`。
- 原文件只保留必要兼容壳或最终删除。

### 阶段 5：淘汰 legacy

删除顺序固定为：

1. strict 主流程分支
2. `legacy_adapter.py` / `legacy_loop.py`
3. 旧 route 特判残留

触发条件不是“代码看起来差不多了”，而是“goldens 在最小覆盖集上稳定通过”。

## Risks and Trade-offs

- 风险：主循环拆分后 trade ordering 细节发生漂移。
  - 对策：golden 对比必须覆盖 trade rows 和 order rows，不只看 perf。
- 风险：route-specific hidden state 被拆坏。
  - 对策：优先把 route runtime 状态显式化到 `route_runtime` 和 `context`。
- 风险：rolling/rank/zscore、市场状态、财务、行业快照模块迁移时出现时间对齐错误。
  - 对策：凡是这类模块迁移，都必须单独做时间可得性审计。
- 风险：为了 bus 化而过度抽象。
  - 对策：第一版只支持当前仓库里已经大量出现的 6 类模块，不做通用 DAG 引擎。

## Acceptance Criteria

- `stage_pipeline.shell` 成为唯一正式日循环壳。
- `foundation_shell.py` 成为主系统到执行总线的唯一兼容门。
- 新实验逻辑只能通过 provider path 或 pipeline built-in module path 接入。
- `portfolio_simulator_strict.py` 只保留过渡 shim 职责并进入删除路径。
- `portfolio_builder.py` 不再承载完整主循环与混合职责。
- baseline goldens 下：
  - `orders` 一致
  - `trades` 一致
  - `NAV` 一致
  - `perf` 一致
  - `counters` 一致
- 审计检查确认没有引入未来函数、时间错位或成交假设变化。

## Open Questions

- 多因子 route 最终是继续走 provider path，还是拆成 provider + built-in rankers/gates 的混合模式。
- `ExecutionIntent` 是否需要直接包含 stage-by-stage audit refs，还是只保留轻量摘要。
- 哪些 route-specific counters 需要晋升为正式契约字段，哪些只保留在 debug artifact。
