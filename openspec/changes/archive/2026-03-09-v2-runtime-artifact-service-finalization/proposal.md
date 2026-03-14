## Why

后端主执行链虽然已经收敛成单一路径，但脚本层和内部 helper 仍直接 import endpoint 层函数，如 `_run_backtest_v2_experiment_sync` 和 `stabilize_experiment_result`。这意味着 API 还承担着运行服务和产物服务的双重职责，分层没有真正收口，也阻碍后续继续清理 legacy 壳。

## What Changes

- 抽取 `experiment-runtime-service`，承接运行前编译、实验执行、结果目录准备和运行返回组装。
- 抽取 `experiment-artifact-service`，承接实验产物稳定化、manifest 更新、标准产物补齐与协议写盘。
- 将 `_experiment_runner_api.py` 收口为 public contract 校验与 thin wrapper。
- 将脚本层、内部 helper、基线门禁迁移到 core service import，不再依赖 endpoint function。
- 保持 `config_json -> experiment_id -> manifest/artifacts` 契约不变，并继续以 `exp_20260308_021045840_cde0` 作为基线门禁。

## Capabilities

### New Capabilities
- `experiment-runtime-service`: 定义单次实验运行服务的输入、输出、配置编译、运行调用和错误边界。
- `experiment-artifact-service`: 定义实验产物稳定化、manifest 写入、标准产物补齐和脚本共享访问边界。

### Modified Capabilities
- `single-run-pipeline`: 单次回测公开执行路径将由 API thin wrapper 调用运行服务，而不是由 endpoint 本身承载主要编排。
- `artifact-protocol-convergence`: 产物稳定化的 owner 从 endpoint 工具函数收口为核心 artifact service，但不改变 artifact 协议本身。

## Impact

- 运行入口：`backend/api/endpoints/_experiment_runner_api.py`
- 产物稳定化：`backend/api/endpoints/backtest_v2_artifacts.py`
- core service：`backend/core/tools/**` 或新建 `backend/core/services/**`
- 脚本与门禁：`backend/scripts/_internal_helper.py`, `backend/scripts/baseline_regression_check.py`, `backend/scripts/report_consistency_check.py` 及研究脚本
- 验证对象：`exp_20260308_021045840_cde0`
