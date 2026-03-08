# Internal Shim Boundary Freeze Map (2026-03-08)

## 结论

以下 shim 进入 `internal-only` 冻结期。后续允许迁调用者、允许缩边界，不允许继续往里长新产品逻辑。

## Freeze Map

| Shim | Owner | 当前 live callers | 替代入口 | Delete gate |
|---|---|---|---|---|
| `backend/api/endpoints/_experiment_runner_api.py` | 公开运行面兼容层 | `backtest_v2.py`、`test_public_surface_convergence.py`、`run_breakout_next_stage_research.py`、`run_dynamic_sizing_experiments.py`、`run_market_state_segmentation_experiments.py`、`internal_script_helper.run_internal_experiment_sync` | 公开产品入口继续走 `backtest_v2.py`；内部脚本统一走 `internal_script_helper.run_internal_experiment_sync` | 研究脚本迁出私有 import，且公开运行面进一步下沉为稳定 service boundary 后 |
| `backend/api/endpoints/_config_governance.py` | 配置 provenance 兼容层 | `_config_store.py`、`_experiment_runner_api.py`、`test_schema_and_artifacts.py`、`internal_script_helper.load_saved_config_record_internal` | 内部脚本统一走 `internal_script_helper.load_saved_config_record_internal` | `_config_store` 与旧配置治理逻辑下线后 |
| `backend/api/endpoints/_candidate_presets.py` | 锁定 candidate 兼容层 | `_experiment_runner_api.py`、`internal_script_helper.candidate_presets_api` | 研究脚本统一走 `internal_script_helper.candidate_presets_api` | 锁定 candidate 入口退出公开运行面，相关研究脚本迁完后 |
| `backend/api/endpoints/backtest_v2_artifacts.py` | 实验目录补全兼容层 | `_experiment_runner_api.py`、`test_schema_and_artifacts.py`、`test_backtest_v2_artifacts.py`、`run_breakout_atr_stop_candidate.py`、`run_breakout_multi_alpha_research.py`、`internal_script_helper.stabilize_internal_experiment_result` | 内部脚本优先走 `internal_script_helper.stabilize_internal_experiment_result` | 研究脚本迁完，实验目录 writer 进一步收敛后 |
| `backend/core/report/report_generator.py` | optional HTML 导出层 | `backtest_v2_artifacts.py`、`run_breakout_multi_alpha_research.py`、`internal_script_helper.ensure_optional_report` | 内部诊断统一走 `internal_script_helper.ensure_optional_report` | `report.html` 完全降级为离线导出物且无脚本直连后 |

## 冻结规则

- shim 只接受调用者收口，不接受新功能扩张。
- 新脚本如果仍需兼容能力，必须接入 `backend/core/tools/internal_script_helper.py`，不能再直接 import shim。
- `report.html` 仍允许作为内部诊断 artifact 存在，但只能通过 manifest/helper 作为 optional artifact 访问。

## 本轮已完成的收口

- `baseline_regression_check.py` 已改走 `internal_script_helper.run_internal_experiment_sync`
- `baseline_regression_check.py` 已改走 `internal_script_helper.load_saved_config_record_internal`
- `run_clean_data_standard_reruns.py` 已改走 `candidate_presets_api` 与 `stabilize_internal_experiment_result`
- `report_consistency_check.py` 已改走 `ensure_optional_report` 与 `read_json_artifact`
