## 1. runtime service 抽离

- [x] 1.1 设计核心 runtime service 的输入/输出契约，覆盖同步运行、异步运行和 preview 共享逻辑。
- [x] 1.2 从 `_experiment_runner_api.py` 中抽离运行期主要编排，形成可供 API 和脚本复用的 service 入口。

## 2. artifact service 抽离

- [x] 2.1 设计核心 artifact service 的输入/输出契约，覆盖标准产物补齐、manifest 写入和实验目录稳定化。
- [x] 2.2 从 `backtest_v2_artifacts.py` 中抽离稳定化主逻辑，形成可供 API 和脚本复用的 service 入口。

## 3. API thin wrapper 收口

- [x] 3.1 将 `_experiment_runner_api.py` 收口为请求校验、service 调用和 HTTP response 包装。
- [x] 3.2 将 artifact 相关 endpoint 收口为 service 调用与读取包装，不再承载主稳定化逻辑。

## 4. 脚本迁移

- [x] 4.1 迁移 `_internal_helper.py`、`baseline_regression_check.py`、`report_consistency_check.py` 到 core service import。
- [x] 4.2 迁移仍在维护的研究脚本，确保 `backend/scripts/**` 不再直接 import endpoint function。

## 5. 验证

- [x] 5.1 使用 `exp_20260308_021045840_cde0` 执行 baseline compare，确认核心产物等价。
- [x] 5.2 检查脚本、API 和异步 job 路径都已共享同一 runtime/artifact service。
