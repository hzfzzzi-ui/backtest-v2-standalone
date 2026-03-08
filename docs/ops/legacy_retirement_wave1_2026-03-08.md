# Legacy Retirement Wave1 (2026-03-08)

## 结论

wave1 只执行一个真实 retirement：删除 `backend/scripts/run_alpha_v1.py`。  
其余 shim 和研究脚本仍保留在 active tree，不进入本 wave。

## 删除对象

| Target | 状态 | 证据 | 替代路径 |
|---|---|---|---|
| `backend/scripts/run_alpha_v1.py` | `retired` | active backend/tests/frontend 源码中无 live caller；公开产品真相已收敛为 `config_json -> experiment_id -> manifest/artifact`；该脚本此前已被冻结且调用即失败 | 产品运行改走公开 `config_json`；若将来还需要类似研究流程，应新建基于当前契约的研究脚本 |

## 零 live caller 证据

- 事实：`backend` active 源码中已不存在 `run_alpha_v1.py` 文件，也不存在其他 backend live caller。
- 事实：`tests` 与 active spec 中仅保留“已退役”断言和状态说明，不再作为运行调用者。
- 事实：archive 目录、change 文档和 research 文档中仍保留历史引用，这些不是 active caller。

## Wave1 不删除清单

| Module | 原因 |
|---|---|
| `backend/api/endpoints/_experiment_runner_api.py` | 仍被公开路由、internal helper 和多支研究脚本使用 |
| `backend/api/endpoints/_config_governance.py` | 仍被 `_config_store.py`、`_experiment_runner_api.py` 与 internal helper 使用 |
| `backend/api/endpoints/_candidate_presets.py` | 仍被 `_experiment_runner_api.py` 与 internal helper 使用 |
| `backend/api/endpoints/backtest_v2_artifacts.py` | 仍承担实验目录补全和部分研究脚本兼容 |
| `backend/core/report/report_generator.py` | 仍被 optional report 导出链路使用 |
| `backend/scripts/baseline_regression_check.py` | 基线门禁核心工具 |
| `backend/scripts/run_clean_data_standard_reruns.py` | clean-data 标准重跑工具 |
| `backend/scripts/report_consistency_check.py` | 内部诊断工具 |
| `backend/scripts/run_breakout_next_stage_research.py` | 仍直接依赖 `_experiment_runner_api` |
| `backend/scripts/run_dynamic_sizing_experiments.py` | 仍直接依赖 `_experiment_runner_api` |
| `backend/scripts/run_market_state_segmentation_experiments.py` | 仍直接依赖 `_experiment_runner_api` |

## Gate

wave1 只有在以下条件同时满足时才可接受：

1. `backend/scripts/run_alpha_v1.py` 从 active tree 删除。
2. active spec 不再声明系统 SHALL 提供 `run_alpha_v1.py`。
3. targeted checks 能阻止该脚本被悄悄加回 active tree。
4. 基线 `exp_20260308_021045840_cde0` 复跑后，核心产物继续 `PASS`，若有 `WARN` 仅允许 `report.html` 诊断漂移。
