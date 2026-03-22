## MODIFIED Requirements

### Requirement: 实验运行必须通过核心 runtime service
系统 MUST 提供核心实验运行服务，承接单次实验的配置编译结果、运行调用和返回结果组装。脚本层与 API 层 SHALL 通过该 service 发起实验运行，而不是直接共享 endpoint 内部函数。runtime service MUST 允许正式 baseline 注册流程通过工作台配置快照显式传入 `data_source.data_role = v2_canonical`，并保持 `membership_mode = PIT_DYNAMIC` 的严格历史成员加载口径。

#### Scenario: API 发起实验运行
- **WHEN** 用户调用 `POST /api/backtest_v2/experiment/run` 或 `run_async`
- **THEN** API 层 SHALL 调用核心 runtime service
- **THEN** endpoint 本身 SHALL NOT 承担主要运行编排

#### Scenario: 脚本发起实验运行
- **WHEN** baseline gate、consistency check 或研究脚本发起实验运行
- **THEN** 脚本 SHALL 调用核心 runtime service
- **THEN** 脚本 SHALL NOT 直接 import `_experiment_runner_api` 内部函数

#### Scenario: baseline_V10.2 以 v2 canonical 运行
- **WHEN** 正式 baseline 注册流程运行 `baseline_V10.2`
- **THEN** runtime service MUST 接收 `data_source.data_role = v2_canonical`
- **THEN** runtime service MUST 使用 `membership_mode = PIT_DYNAMIC` 的严格历史成员加载口径
- **THEN** 运行结果 MUST 正常落成 linked experiment 产物
