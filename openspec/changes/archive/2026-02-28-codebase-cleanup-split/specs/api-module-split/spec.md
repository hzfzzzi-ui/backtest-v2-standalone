## ADDED Requirements

### Requirement: 提取共享工具模块 _utils.py

系统 SHALL 将以下跨模块共享函数提取到 `backend/api/endpoints/_utils.py`：
- `sanitize_json` — 统一两处重复定义（backtest_v2.py 和 backtest_v2_artifacts.py）
- `_coerce_number`
- `_load_json_file`
- `_hash_json`
- `_sanitize_for_json`
- 相关常量：`_ROWS_NUMERIC_FIELDS`, `_ROWS_INTEGER_FIELDS`, `_PIPELINE_STAGE_NAMES`

#### Scenario: 工具函数统一来源
- **WHEN** `_utils.py` 创建完成
- **THEN** `backtest_v2.py` 和 `backtest_v2_artifacts.py` 都从 `_utils` import `sanitize_json`，不再各自定义

### Requirement: 提取路径辅助模块 _paths.py

系统 SHALL 将以下路径函数提取到 `backend/api/endpoints/_paths.py`：
- `_repo_root`, `_bt_root`, `_results_root`, `_configs_root`, `_execution_root`
- `_jobs_root`, `_job_file`
- `_experiments_root`

#### Scenario: 路径函数统一来源
- **WHEN** `_paths.py` 创建完成
- **THEN** `backtest_v2.py` 和 `backtest_v2_artifacts.py` 中重复的 `_repo_root`/`_results_root` 定义被消除

### Requirement: 提取 Job 管理模块 _job_store.py

系统 SHALL 将异步任务管理逻辑提取到 `backend/api/endpoints/_job_store.py`：
- `_JOBS` 字典和 `_JOBS_LOCK`
- `_persist_job`, `_load_job_from_disk`
- `_create_job`, `_update_job`, `_is_cancel_requested`, `_mark_job_canceled`, `_job_payload`

#### Scenario: Job 管理独立运行
- **WHEN** 用户通过 `/api/backtest_v2/experiment/run_async` 提交异步任务
- **THEN** Job 正常创建、轮询状态、取消操作均通过 `_job_store` 模块完成

### Requirement: 提取配置 CRUD 模块 _config_store.py

系统 SHALL 将配置存储逻辑提取到 `backend/api/endpoints/_config_store.py`：
- `_flow_script_config_json`, `_ensure_builtin_flow_script_config`
- 配置路由处理函数：save / get / list configs

#### Scenario: 配置保存和加载正常
- **WHEN** 用户通过前端保存或加载配置
- **THEN** `/api/backtest_v2/configs` 的 POST/GET 路由正常工作

### Requirement: 提取实验执行模块 _experiment_runner_api.py

系统 SHALL 将回测执行逻辑提取到 `backend/api/endpoints/_experiment_runner_api.py`：
- `BacktestV2ExperimentRequest` 模型
- `_load_base_config`, `_to_int_or_default`, `_build_runtime_cfg_from_workbench`
- `_run_backtest_v2_experiment_sync`, `_attach_run_profile_summary`
- `_run_backtest_v2_experiment_job`

#### Scenario: 同步和异步回测执行正常
- **WHEN** 用户点击前端"运行回测"按钮
- **THEN** 同步执行（`run_backtest_v2_experiment`）和异步执行（`run_async`）均正常工作

### Requirement: 提取实验历史模块 _experiment_history.py

系统 SHALL 将实验归档逻辑提取到 `backend/api/endpoints/_experiment_history.py`：
- `_read_index`, `_write_index`
- 路由处理函数：list / get_report / delete / clear_all experiments

#### Scenario: 实验历史管理正常
- **WHEN** 用户在前端查看历史实验列表或删除实验
- **THEN** `/api/backtest_v2/experiments` 的 GET/DELETE 路由正常工作

### Requirement: 主文件瘦身后路由完整

拆分完成后，`backtest_v2.py` 主文件 SHALL 仅保留：
- `router` 定义和中间件
- 市场数据路由（industries, benchmark_series, symbol_series, stock_names）
- validate_data 路由及其专属辅助函数
- execution/preview 路由及其专属辅助函数
- artifact_read 路由
- 各子模块路由的 `router.include_router()` 注册

#### Scenario: 拆分后所有 19 个路由可访问
- **WHEN** 所有子模块拆分完成
- **THEN** 通过 `curl` 测试所有 19 个路由端点返回正确 HTTP 状态码（200/404/422），无 500
