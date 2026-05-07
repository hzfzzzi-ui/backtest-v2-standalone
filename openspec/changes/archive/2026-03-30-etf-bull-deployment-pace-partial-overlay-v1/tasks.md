## 1. 合同与执行链

- [x] 1.1 在 ETF contract 中新增 `bull_partial_overlay_pace_ratio=0.5`，并将 `BULL` 状态下的 `deployment_pace` 改为 `floor + 0.5 * overlay`。DoD: `resolve_etf_beta_exposure_semantics()` 能输出新的 `BULL` pace、ratio 和 pace mode；验证: `tests/unit/test_etf_beta_contract.py`；风险: 不得影响 `TRANS_UP`、`LIGHT`、`TRANS_DOWN`、`RISK_OFF` 的 pace 公式。
- [x] 1.2 贯通 provider / daily accounting / orders 元数据，把 `bull_partial_overlay_pace_ratio` 与 `bull_pace_mode` 写入正式产物。DoD: `portfolio_daily.csv` 与 `orders.csv` 能直接看到 `BULL` partial overlay pace 生效证据；验证: `tests/unit/test_cn_etf_beta_signal_provider.py`、`tests/unit/test_bridge_adapter_accounting.py`、`tests/unit/test_experiment_runner_daily_schema.py`；风险: 不得重新引入第二套 target 真相。

## 2. 审计与归因

- [x] 2.1 扩展 research audit，对 `BULL` 输出 partial overlay pace 摘要，并与现有 `pace_policy_gap / rebalance_timing_gap / execution_residual_gap` 对齐。DoD: `audit.json` 能回答 `BULL` 下 partial overlay pace 是否缩小了 `pace_policy_gap`；验证: `tests/unit/test_research_audit_contract.py`；风险: 不得把 `BULL` 的新字段误扩展到 `TRANS_UP`。
- [x] 2.2 继续保留 `TRANS_UP` 的 `single-seat core recovery` 审计语义，确保本次变更不会被误解为 `TRANS_UP` 也放开 overlay。DoD: `audit.json` 的 `TRANS_UP` 摘要与合同仍一致；验证: `tests/unit/test_research_audit_contract.py`；风险: 不得把状态边界重新混合。

## 3. 回归与正式实验

- [x] 3.1 补齐受影响单测并完成回归。DoD: contract/provider/accounting/audit/schema 相关单测全部通过；验证: `pytest tests/unit/test_semantic_config_compiler.py tests/unit/test_etf_beta_contract.py tests/unit/test_cn_etf_beta_signal_provider.py tests/unit/test_bridge_adapter_accounting.py tests/unit/test_research_audit_contract.py tests/unit/test_experiment_runner_daily_schema.py -q`；风险: 不得引入 timing 或 artifact schema 回归。
- [x] 3.2 重跑正式 ETF study，并给出变更前后 `BULL` 的 `target/floor/overlay/pace/actual/gap` 对照摘要。DoD: 产出新实验并明确汇报 `CAGR`、`MaxDD`、`BULL avg_pace_policy_gap`、`BULL avg_actual_exposure` 的变化；验证: `study_run etf/cn_etf_first_wave_core --window 1626 --variant CORE --skip-baseline-append`；风险: 必须明确这是 pace 合同优化，不得误报为整体策略定型。
