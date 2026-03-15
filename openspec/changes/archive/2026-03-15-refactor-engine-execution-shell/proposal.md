## Why

当前回测执行层同时存在 strict 壳、legacy 壳和新 stage pipeline 骨架，已经形成“双轨甚至三轨”执行面。现在必须尽快把执行总线统一，否则新实验会继续绕过总线堆进主循环，且最敏感的 10.1 价格型信号口径会持续暴露在结构漂移风险下。

## What Changes

- 将 `stage_pipeline` 明确为唯一正式执行总线，并将 [foundation_shell.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/engine_compat/foundation_shell.py) 明确为主系统唯一执行入口。
- 将新实验的合法扩展入口限制为 `provider path` 和 `pipeline built-in module path` 两类。
- 将 `order_planning`、`fill_accounting`、`daily_accounting` 提升为正式 contract 边界。
- 将 [portfolio_simulator_strict.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/engine_vector/portfolio_simulator_strict.py) 和 legacy loop 压缩为待删除 shim，并以 golden 覆盖作为删除前提。
- 为执行总线重构补齐最小 golden 覆盖集和时间对齐审计红线。

## Capabilities

### New Capabilities
- `execution-shell-unification`: 定义唯一正式执行总线、唯一执行入口和 legacy 删除纪律。
- `execution-bus-extension-model`: 定义 provider path / pipeline built-in module path 双入口和单轮实验归因纪律。
- `execution-contract-goldens`: 定义 RuntimePlan、ExecutionIntent、AccountingSnapshot 契约及 golden 覆盖门槛。

### Modified Capabilities
- 无

## Impact

- 影响引擎核心文件：[portfolio_simulator_strict.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/engine_vector/portfolio_simulator_strict.py)、[portfolio_builder.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/portfolio/portfolio_builder.py)、[foundation_shell.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/engine_compat/foundation_shell.py)、[shell.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/stage_pipeline/shell.py)。
- 影响 route/provider 注册层和未来 study/脚本接入方式。
- 影响 golden 测试、回放对比和时间对齐审计。
- 不应改变任何策略公式、价格型信号时点、成交规则或 baseline 输出口径。
