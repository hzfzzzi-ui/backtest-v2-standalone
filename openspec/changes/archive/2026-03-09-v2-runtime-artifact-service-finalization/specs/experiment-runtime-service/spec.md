## ADDED Requirements

### Requirement: 实验运行必须通过核心 runtime service

系统 MUST 提供核心实验运行服务，承接单次实验的配置编译结果、运行调用和返回结果组装。脚本层与 API 层 SHALL 通过该 service 发起实验运行，而不是直接共享 endpoint 内部函数。

#### Scenario: API 发起实验运行
- **WHEN** 用户调用 `POST /api/backtest_v2/experiment/run` 或 `run_async`
- **THEN** API 层 SHALL 调用核心 runtime service
- **THEN** endpoint 本身 SHALL NOT 承担主要运行编排

#### Scenario: 脚本发起实验运行
- **WHEN** baseline gate、consistency check 或研究脚本发起实验运行
- **THEN** 脚本 SHALL 调用核心 runtime service
- **THEN** 脚本 SHALL NOT 直接 import `_experiment_runner_api` 内部函数

### Requirement: runtime service 必须保持配置真相与实验输出不变

runtime service 下沉 MUST 保持 `config_json -> runtime plan -> run_experiment -> experiment_id` 主链不变，不得引入新的配置来源或改变基线实验结果口径。

#### Scenario: baseline 复跑
- **WHEN** 使用基线配置复跑 `exp_20260308_021045840_cde0`
- **THEN** 核心 compare 结果 SHALL 继续通过
- **THEN** 不得新增核心产物漂移
