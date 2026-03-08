# 后端重构旧代码淘汰门槛

## 目的

`exp_20260308_021045840_cde0` 是当前后端重构锁定基线。  
任何旧代码淘汰都必须先满足“新主线已覆盖职责”与“基线门禁未漂移”两个前置条件。

固定门禁命令：

`python backend/scripts/baseline_regression_check.py --rerun --write-to-candidate`

允许推进删除的最低条件：

1. 候选实验对锁定基线的 `portfolio_daily.csv`、`portfolio_trades.csv`、`portfolio_candidates.csv`、`perf.json` 必须为 `PASS`。
2. `config_truth` 必须为 `PASS`。
3. `manifest` 必须能发现 `input_config.json`、`resolved_config.json`、`compiled_plan.json`、`baseline_compare.json`。
4. 若结果为 `WARN`，只能来自 `diagnostic_drift`，当前即 `report.html`。

## 淘汰顺序

### 1. 多配置源入口层

范围：

- `backend/api/endpoints/_experiment_runner_api.py` 中 `config_id`、`runtime_config_json`、`workbench_config`、`config_path` 相关兼容分支
- `backend/api/endpoints/_config_governance.py`
- `backend/api/endpoints/_config_store.py`
- `backend/api/endpoints/_candidate_presets.py`

删除前置条件：

1. 所有公开运行入口都已强制收敛到前端语义 `config_json`。
2. preview 与正式运行共享同一编译链。
3. 基线门禁连续通过。

### 2. 多执行模式外壳

范围：

- `backend/core/tools/experiment_runner.py` 中 legacy 编排兼容片段
- `backend/core/portfolio/portfolio_builder.py` 中 engine mode 分支外壳
- `backend/core/config/models.py` 中仅为 legacy mode 保留的执行模式字段

删除前置条件：

1. `compiled_plan + DataBundle + compatibility shell` 已成为唯一公开运行路径。
2. 锁定基线复跑通过。
3. 新旧路径的输入映射已冻结，不再新增旁路参数。

### 3. 结果兼容补丁层

范围：

- `backend/api/endpoints/backtest_v2_artifacts.py` 中仅为历史兼容保留的补丁逻辑
- `backend/api/endpoints/_experiment_history.py`
- `backend/core/report/report_generator.py`

删除前置条件：

1. 前端只依赖实验目录稳定产物与 `manifest.json`。
2. `baseline_compare.json` 与配置快照已纳入 manifest。
3. 前端不再把 `report.html` 视为主消费面。

### 4. research-only 策略表面与旧脚本

范围：

- `backend/core/strategies/` 中 research-only 策略
- `backend/scripts/` 中依赖旧入口的实验脚本

删除前置条件：

1. 新 9-stage 主线已覆盖实际使用的策略语义。
2. 旧脚本的运行诉求已有新的公开入口或新文档替代。
3. 基线门禁与最小回归测试都通过。

## 暂不允许删除

- `backend/core/engine_vector/data_matrix.py`
- `backend/core/engine_vector/features.py`
- `backend/core/engine_vector/signal_matrix.py`
- `backend/core/engine_vector/candidate_index.py`
- `backend/core/engine_vector/breakout_signal_provider.py`

这些文件当前仍属于可复用纯计算核。  
在新的 9-stage 计算核完全替代前，只允许抽取和包裹，不允许先删。
