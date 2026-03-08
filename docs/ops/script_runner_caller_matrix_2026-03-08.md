# Script Runner Caller Matrix (2026-03-08)

## 结论

当前脚本/工具调用面按三类治理：

1. `public caller`
2. `internal helper caller`
3. `legacy retired / frozen`

这轮 change 至少覆盖了 `baseline_regression_check.py`、`run_clean_data_standard_reruns.py`、`report_consistency_check.py`、`run_alpha_v1.py` 四个关键调用者。

## 分类矩阵

| Caller | 分类 | 当前入口 | 旧依赖状态 | 说明 |
|---|---|---|---|---|
| `backend/scripts/baseline_regression_check.py` | `internal helper caller` | `backend.core.tools.internal_script_helper.run_internal_experiment_sync` + `load_saved_config_record_internal` | 已去除 `_experiment_runner_api` / `_config_governance` 直连 | 保留为基线门禁与 `baseline_compare.json` 写入工具 |
| `backend/scripts/run_clean_data_standard_reruns.py` | `internal helper caller` | `candidate_presets_api` + `stabilize_internal_experiment_result` + `resolve_internal_results_dir` | 已去除 `_candidate_presets` / `backtest_v2_artifacts` 直连 | 保留为 clean-data 标准重跑工具 |
| `backend/scripts/report_consistency_check.py` | `internal helper caller` | `open_experiment_handle` + `read_json_artifact` + `ensure_optional_report` | 已去除 `report_generator` 直连 | 保留为内部诊断工具；`report.html` 仅视为 optional artifact |
| `backend/scripts/run_alpha_v1.py` | `legacy retired` | 无 | 已从 active tree 删除 | wave1 已执行 retirement，不再保留 stub |
| `frontend/assets/js/backtest_v2.js` + `frontend/assets/js/artifacts.js` | `public caller` | `config_json -> experiment_id -> manifest/artifact` | 不使用旧公开字段 | 这是当前唯一产品真相 |

## 仍待后续收口的直接私有调用者

以下脚本仍直接依赖私有 shim，但不在本 change 的迁移范围内：

| Caller | 当前直连 | 备注 |
|---|---|---|
| `backend/scripts/run_breakout_next_stage_research.py` | `_experiment_runner_api` | 研究脚本，后续 retirement change 处理 |
| `backend/scripts/run_dynamic_sizing_experiments.py` | `_experiment_runner_api` | 研究脚本，后续 retirement change 处理 |
| `backend/scripts/run_market_state_segmentation_experiments.py` | `_experiment_runner_api` | 研究脚本，后续 retirement change 处理 |
| `backend/scripts/run_breakout_atr_stop_candidate.py` | `backtest_v2_artifacts` | 锁定 candidate 研究脚本，后续迁移 |
| `backend/scripts/run_breakout_multi_alpha_research.py` | `backtest_v2_artifacts` + `report_generator` | 研究脚本，后续迁移 |

## 判定规则

- `public caller` 只能使用公开 `config_json -> experiment_id -> manifest/artifact` 表面。
- `internal helper caller` 允许使用 `backend.core.tools.internal_script_helper`，但不允许再直接 import endpoint 私有实现。
- `legacy retired` 已从 active tree 删除，不再作为现行能力存在。
- `frozen legacy script` 仅是过渡状态，不得长期替代真正 retirement。
