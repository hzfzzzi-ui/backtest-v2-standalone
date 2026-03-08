# Legacy Delete Batch Candidates (2026-03-08)

## 结论

Batch #1 已执行完毕：`backend/scripts/run_alpha_v1.py` 已在 wave1 中退役。  
当前文档保留的是“已执行结果”和“后续仍不可删对象”，而不是待办候选池。

## Executed Batch #1

| Candidate | 证据 | 替代入口 | 删除前置条件 | 执行结果 |
|---|---|---|---|---|
| `backend/scripts/run_alpha_v1.py` | active 源码中无其他 live caller；公开运行已收敛；此前已冻结 | 公开运行改走 `config_json -> experiment_id -> manifest/artifact`；如需类似研究流程，应新建基于当前契约的研究脚本 | 1. 零 live caller 证据 2. active spec 同步收敛 3. 基线门禁继续通过 | 已在 `v2-legacy-retirement-wave1` 中退役 |

## 暂不进入后续 wave 的对象

| 模块 | 原因 |
|---|---|
| `backend/api/endpoints/_experiment_runner_api.py` | 仍有公开路由与多支研究脚本 live caller |
| `backend/api/endpoints/_config_governance.py` | 仍被 `_config_store.py`、`_experiment_runner_api.py` 和 internal helper 使用 |
| `backend/api/endpoints/_candidate_presets.py` | 仍被 `_experiment_runner_api.py` 和 internal helper 使用 |
| `backend/api/endpoints/backtest_v2_artifacts.py` | 仍承担公开实验目录补全与部分研究脚本兼容 |
| `backend/core/report/report_generator.py` | 仍被 optional report 导出链路使用 |
| `backend/scripts/baseline_regression_check.py` | 当前基线门禁核心工具，必须保留 |
| `backend/scripts/run_clean_data_standard_reruns.py` | 当前 clean-data 标准重跑工具，必须保留 |
| `backend/scripts/report_consistency_check.py` | 当前内部诊断工具，必须保留 |

## 删除规则

- 候选必须附带零 live caller 证据或明确 frozen 状态。
- 候选必须有替代入口或明确声明“不再保留该能力”。
- 删除动作必须继续通过基线 `exp_20260308_021045840_cde0` 的回归门禁。
