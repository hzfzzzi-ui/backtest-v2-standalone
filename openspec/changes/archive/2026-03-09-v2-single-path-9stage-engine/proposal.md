## Why

当前后端虽然已经收敛到 `config_json -> compiler -> DataBundle -> compatibility shell -> legacy strict core` 的主链，但真正的执行编排仍然混在旧引擎分支和策略特例里，尚未形成“唯一日循环 + 9-stage 总线”的明确运行真相。现在继续删除旧代码或拆 stage，会因为缺少统一执行壳而失去归因能力，并增加未来函数、时间错位和口径漂移风险。

## What Changes

- 新增单路径 9-stage 日循环执行壳，固定公开回测入口的统一编排顺序。
- 定义 stage 模块的输入/输出契约，要求各 stage 只消费 `DayContext + StageInputs`，不直接查库、不直接写盘。
- 将候选流、持仓流与组合构建流在同一日循环下分层组织，保持 `t` 日收盘决策、`t+1` 日开盘成交不变。
- 为 stage 壳增加最小审计与观测面，包括 stage 顺序、可用性、计数摘要和 reason-code 归因入口。
- 在不改核心文件名和基线结果的前提下，把 stage 运行摘要纳入稳定产物协议。
- 明确旧 legacy 编排层的冻结边界；在单路径 stage 壳落地前，不允许继续向旧分支加功能。

## Capabilities

### New Capabilities
- `stage-pipeline-shell`: 定义单路径 9-stage 日循环执行壳、stage I/O 契约和统一编排顺序。

### Modified Capabilities
- `single-run-pipeline`: 公开单次回测入口改为必须进入 stage pipeline shell，不再允许并行公开执行路径。
- `pipeline-data-integrity`: stage 壳中的所有模块必须只消费当日可见的 `DataBundle` 视图，并禁止在日循环内访问数据库或 provider。
- `artifact-protocol-convergence`: 稳定产物协议需表达 stage pipeline 的配置与运行摘要，供前端和治理脚本发现。
- `backtest-audit`: 审计产物需覆盖 stage 壳的执行顺序、T+1 约束和 stage 级异常摘要。

## Impact

- 影响代码主要在 `backend/core/tools/experiment_runner.py`、新的 stage shell/上下文目录、现有 legacy strict engine 包装层、`backend/api/endpoints/backtest_v2_artifacts.py` 和审计产物写盘逻辑。
- 公开 API 语义不新增第二条运行路径，但内部执行将从 compatibility shell 进一步收敛为单路径 stage shell。
- 依赖现有 `exp_20260308_021045840_cde0` 基线门禁；任何实现都必须通过 `python backend/scripts/baseline_regression_check.py --rerun --write-to-candidate`。
