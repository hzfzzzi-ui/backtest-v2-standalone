# Legacy Frozen Scripts (2026-03-08)

## 结论

`backend/scripts/run_alpha_v1.py` 曾在上一轮被列入 `frozen legacy script`，并已在 wave1 中进入 `retired` 状态。

## 冻结原因

- 事实：该脚本通过公开 HTTP `/api/backtest_v2/experiment/run_async` 提交任务。
- 事实：其 payload 仍依赖旧公开字段，如 `config_path`、`workbench_config`、`enable_strength_rank`、`results_dir`。
- 事实：当前公开产品真相已经收敛为 `config_json -> experiment_id -> manifest/artifact`。
- 推断：如果为了保留这支脚本而回填旧公开字段，会直接污染已经收敛的公开契约。

## 当前处理

- frozen 过渡阶段已经结束。
- 该脚本现已从 active tree 删除，不再以 stub 形式保留。
- 不再为该脚本补兼容字段。
- 不再接受基于该脚本的新增功能请求。

## 替代路径

- 面向产品或前端的运行：使用当前公开 `config_json` 运行入口。
- 面向内部研究脚本的过渡能力：只允许通过 `backend/core/tools/internal_script_helper.py` 承接，且不能要求公开 API 恢复旧字段。

## 退役结果

- `run_alpha_v1.py` 已在 `v2-legacy-retirement-wave1` 中退役。
- wave1 retirement ledger 见 [legacy_retirement_wave1_2026-03-08.md](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/docs/ops/legacy_retirement_wave1_2026-03-08.md)。
