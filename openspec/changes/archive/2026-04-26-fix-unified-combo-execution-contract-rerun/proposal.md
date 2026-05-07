## Why

当前 A_STOCK_ETF_V1 基线复跑不能稳定复现已登记的执行合同：个股腿因为 `execution_overrides` 没进入子腿 runtime 而关闭 final_score/MF 排名，ETF 腿因为语义重编译被无条件改写为 phase1 配置而偏离已批准的 R1 研究口径。

这会让“唯一执行合同”失去可复现性，导致同一基线在不同入口下产生不同绩效，必须先修复合同执行链路再继续分析收益。

## What Changes

- unified combo 的 `execution_contract` 将显式携带每个子腿进入执行壳所需的 `execution_overrides`，而不只保存 `runtime_config`。
- unified combo 运行子腿时必须从组件执行合同组装请求，确保 `runtime_config_json` 路径也能保留排名、仓位等执行覆盖参数。
- baseline 复跑入口必须解析 `baseline.json.execution_contract_ref` 指向的正式 `execution_contract.json`，不能只用 `baseline_config_snapshot.json` 重新推导执行真相。
- ETF 子腿编译不得无条件把已有 `cn_etf_broad_based_standalone_mainline_entry` 改写为 `phase1_bucket_allocation`；只有输入明确属于 phase1 或缺省正式 phase1 anchor 时才应用 phase1 规范化。
- 新增回归测试，覆盖个股 final_score/MF 排名开关、ETF R1 口径保留、baseline execution contract 引用解析。

## Capabilities

### New Capabilities
- `baseline-execution-contract-replay`: 定义 baseline 复跑必须通过 `execution_contract_ref` 解析正式执行合同。

### Modified Capabilities
- `runtime-boundary-contracts`: 明确 execution contract 必须包含子腿执行壳所需的 execution overrides。
- `api-runtime-config-compilation`: 明确 ETF 子腿编译不得无条件把已声明的 R1 研究配置提升为 phase1 配置。

## Impact

- 影响后端运行链路：`backend/api/backtest_v2/runner_output_helpers.py`、`backend/api/backtest_v2/runner_config_bundle.py`、`backend/core/services/cn_stock_etf_unified_runtime_service.py`、`backend/core/services/experiment_runtime_service.py`。
- 影响基线读取或复跑辅助：`backend/core/tools/baseline_access.py` 及相关测试。
- 影响回归测试：`tests/unit/test_cn_stock_etf_unified_runtime_service.py`、`tests/unit/test_execution_contract_goldens.py` 或新增针对 baseline replay 的单元测试。
- 不改变策略公式、信号时点、成交时点、行情数据源和现有已归档实验产物。
