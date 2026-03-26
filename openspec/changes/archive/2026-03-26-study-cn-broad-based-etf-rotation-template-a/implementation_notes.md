## 实现范围

本轮完成了模板 A 的 A0 可直跑版研究接入与首轮对照，不包含 A1 正式资产池扩展。

已落地内容：

- `cn_etf_beta_signal_provider` 支持模板 A 所需的月频调仓、`12M/6M/3M` 相对强弱、`MA200 + 12M>0` 绝对过滤。
- `governed_a_share.etf_beta` 扩展了模板元信息字段：
  - `template_id`
  - `template_asset_pool_version`
  - `template_role_map`
  - `template_proxy_map`
  - `template_target_formal_symbols`
  - `growth_seat_symbol`
  - `relative_strength_mid_window`
  - `relative_strength_mid_weight`
- `research_audit` 现在会输出模板 A 研究证据，包括：
  - role map
  - proxy map
  - target formal symbols
  - growth seat
  - 评分窗口与权重
  - 绝对过滤模式
  - fallback 配置
  - under-deploy 原因
- 新增 study：
  - `research/studies/etf/cn_broad_based_rotation_template_a.study.yaml`

## 首轮结果

主开发窗口 `2016-2026` 的 A0 首轮对照结果：

- `A0_GEM_TOP2_BOND`
  - `CAGR 2.88%`
  - `MaxDD -12.26%`
  - `Sharpe 0.347`
  - 当前冠军
- `A0_GEM_TOP2_CASH`
  - `CAGR 2.84%`
  - `MaxDD -13.72%`
  - `Sharpe 0.332`
- `A0_STAR50_TOP2_CASH`
  - `CAGR -0.53%`
  - `MaxDD -23.04%`
  - `Sharpe -0.032`
- `A0_GEM_TOP1_CASH`
  - `CAGR 0.00%`
  - `MaxDD 0.00%`
  - `Sharpe 0.000`
  - `trades = 0`

对应汇总产物：

- `outputs/ops/study_cn_broad_based_etf_rotation_template_a_20260326/variant_compare.csv`
- `outputs/ops/study_cn_broad_based_etf_rotation_template_a_20260326/summary.json`

## 事实结论

1. `159915.SZ` 作为成长位明显优于 `588000.SH`
2. `Top2` 明显优于 `Top1`
3. `511010.SH` fallback 相比纯 `cash` 有小幅正改善
4. A0 的冠军已经能跑出正 CAGR，但仍然显著弱于当前股票 alpha 主线
5. `audit.json` 已能直接证明模板 A 规则真的生效，而不是产物后处理猜出来的

## A1 触发条件

A1 目前不应推进实现，只有在以下条件满足后才进入下一轮：

1. 标准中证1000 ETF 已接入本地 `cn_etf` 正式池，并完成历史覆盖验证
2. 标准红利 ETF 已接入本地 `cn_etf` 正式池，并完成历史覆盖验证
3. A1 接入后，重新跑三组最小对照：
   - 成长位：`159915` vs `588000`
   - 组合构建：`Top1` vs `Top2`
   - fallback：`cash` vs `511010`

## 风险

- 当前 A0 仍然使用 `512100` 和 `512890` 作为 proxy，不能把它误写成标准中证1000 / 红利正式池。
- 月频 `Top2` 在 A0 上已成立，但还不能直接推断 A1 一定成立。
- 本轮结果说明模板 A 比当前 ETF V1 更像正式 beta 研究线，但还不能单独升格成正式收益主线。

## 验证

已完成：

- `pytest tests/unit/test_cn_etf_beta_signal_provider.py tests/unit/test_semantic_config_compiler.py tests/unit/test_research_audit_contract.py -q`
- `python -m backend.cli study_run etf/cn_broad_based_rotation_template_a --dry-run`
- `docker exec backtest-v2-standalone python -m backend.cli study_run etf/cn_broad_based_rotation_template_a`
- `openspec validate study-cn-broad-based-etf-rotation-template-a --type change --strict`

## 回退

如需回退本轮实现，核心撤回这些文件即可：

- `backend/core/engine_vector/cn_etf_beta_signal_provider.py`
- `backend/core/config/cn_a_governed_mainline.py`
- `backend/core/audit/research_audit.py`
- `backend/api/backtest_v2/semantic_config_schema.py`
- `research/studies/etf/cn_broad_based_rotation_template_a.study.yaml`
- `tests/unit/test_cn_etf_beta_signal_provider.py`
- `tests/unit/test_semantic_config_compiler.py`
- `tests/unit/test_research_audit_contract.py`
