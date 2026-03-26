## 范围

本轮实现只完成 `A0 -> A0 V2` 的结构化改造，不扩 ETF 池，不接 unified runtime，不重做旧 ETF V1 / 稳定器 V2。

实际落地包括：

- 在 [backend/core/engine_vector/cn_etf_beta_signal_provider.py](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/engine_vector/cn_etf_beta_signal_provider.py) 新增 `core_slot + growth_slot` 选择语义。
- 在 [backend/api/backtest_v2/semantic_config_schema.py](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/api/backtest_v2/semantic_config_schema.py) 接通：
  - `proxy_replacement_mode`
  - `formal_replacement_pairs`
  - `core_slot_symbols`
  - `growth_slot_symbols`
- 在 [backend/core/config/cn_a_governed_mainline.py](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/config/cn_a_governed_mainline.py)、[backend/core/audit/research_audit.py](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/audit/research_audit.py)、[backend/api/backtest_v2/artifacts_finalize.py](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/api/backtest_v2/artifacts_finalize.py) 补齐槽位级证据链。
- 新增研究入口：[research/studies/etf/cn_broad_based_rotation_template_a0_core_satellite_v2.study.yaml](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/research/studies/etf/cn_broad_based_rotation_template_a0_core_satellite_v2.study.yaml)。

## 结果

正式产物在：

- [variant_compare.csv](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/ops/study_cn_broad_based_etf_rotation_a0_core_satellite_v2_20260326/variant_compare.csv)
- [summary.json](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/ops/study_cn_broad_based_etf_rotation_a0_core_satellite_v2_20260326/summary.json)

本轮最重要的事实：

- `A0V2_NONE` 是 A0 V2 冠军：
  - `CAGR 1.72%`
  - `MaxDD -10.86%`
  - `Sharpe 0.282`
- `A0V2_DIVIDEND_PROXY_ONLY` 次优：
  - `CAGR 1.03%`
  - `MaxDD -10.85%`
  - `Sharpe 0.180`
- `A0V2_CSI1000_PROXY_ONLY` 明显更差：
  - `CAGR 0.06%`
  - `MaxDD -14.07%`
  - `Sharpe 0.048`
- `A0V2_FULL_STANDARD_SWAP` 最差：
  - `CAGR -0.62%`
  - `MaxDD -16.91%`
  - `Sharpe -0.036`

和旧 A0 胜出版的 overlap 参考相比：

- 旧 A0 胜出版 `A0_GEM_TOP2_BOND` 在同类 overlap 参考约为：
  - `CAGR 2.09%`
  - `MaxDD -10.86%`
  - `Sharpe 0.300`

正式判断：

- `A0 V2` 结构化以后仍能跑出正收益，但**整体弱于旧 A0 胜出版**。
- `CSI1000` 的标准替换是当前主要拖累项。
- `FULL_STANDARD_SWAP` 不值得继续推进。
- 这条线**不建议升格**；当前 ETF 主研究线仍应保留旧 `A0_GEM_TOP2_BOND`。

## 关键修正

实现过程中发现一个真实口径问题：

- study 初版把结束日写成了 `2026-03-25`
- 但 proxy 池共同覆盖只到 `2026-03-24`
- 这会让仍持有 proxy 的变体在最后一天被估成 `0`

因此本轮已把研究窗口修正为共同覆盖窗口：

- `2021-03-31 ~ 2026-03-24`

这一步是必要修正，不是策略优化。

## 验证

已完成：

- `pytest tests/unit/test_cn_etf_beta_signal_provider.py tests/unit/test_research_audit_contract.py tests/unit/test_semantic_config_compiler.py -q`
- `python -m backend.cli study_run etf/cn_broad_based_rotation_template_a0_core_satellite_v2 --dry-run`
- `docker exec backtest-v2-standalone python -m backend.cli study_run etf/cn_broad_based_rotation_template_a0_core_satellite_v2`
- `openspec validate study-cn-broad-based-etf-rotation-a0-core-satellite-v2 --type change --strict`
- `openspec instructions apply --change "study-cn-broad-based-etf-rotation-a0-core-satellite-v2"`

槽位证据链抽样已确认出现在：

- [run_meta.json](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/experiments/exp_20260326_041231095_fd81/run_meta.json)
- [audit.json](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/experiments/exp_20260326_041231095_fd81/audit.json)

可见字段包括：

- `proxy_replacement_mode`
- `core_slot_selected_symbol`
- `growth_slot_selected_symbol`
- `slot_selection_reason_codes`
- `slot_under_deploy_reason_codes`
- `core_slot_target_exposure`
- `growth_slot_target_exposure`

## 风险

- 当前 `A0 V2` 仍然长期 `UNDERDEPLOYED`，不是成熟正式 beta 层。
- `159845.SZ` 历史短，决定了这条研究线只能看 overlap 窗口。
- 这轮只证明了“结构化持仓 + 单点替换”的研究结论，不代表 unified runtime 已准备好消费它。

## 回退

如果要回退这轮，核心撤回：

- [backend/core/engine_vector/cn_etf_beta_signal_provider.py](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/engine_vector/cn_etf_beta_signal_provider.py)
- [backend/api/backtest_v2/semantic_config_schema.py](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/api/backtest_v2/semantic_config_schema.py)
- [backend/core/config/cn_a_governed_mainline.py](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/config/cn_a_governed_mainline.py)
- [backend/core/audit/research_audit.py](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/audit/research_audit.py)
- [backend/api/backtest_v2/artifacts_finalize.py](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/api/backtest_v2/artifacts_finalize.py)
- [research/studies/etf/cn_broad_based_rotation_template_a0_core_satellite_v2.study.yaml](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/research/studies/etf/cn_broad_based_rotation_template_a0_core_satellite_v2.study.yaml)

并删除本轮产物目录：

- [study_cn_broad_based_etf_rotation_a0_core_satellite_v2_20260326](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/ops/study_cn_broad_based_etf_rotation_a0_core_satellite_v2_20260326)
