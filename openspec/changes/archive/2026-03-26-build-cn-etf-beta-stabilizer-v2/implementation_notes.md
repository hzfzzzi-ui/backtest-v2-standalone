## Summary

`build-cn-etf-beta-stabilizer-v2` 已完成实现与最小 AB。

本轮收口的重点不是“把 ETF 直接做成高收益主线”，而是验证：

1. ETF 收益差是否主要由部署不足导致。
2. `max_selected_symbols = 2` 与 `511010` fallback 是否能把 ETF 从“轻仓战术轮动”拉近到“beta 稳定器”。

## What Changed

### 1. ETF provider 支持 V2 并持与 partial fallback fill

核心文件：
- `backend/core/engine_vector/cn_etf_beta_signal_provider.py`

本轮新增：
- `max_selected_symbols = 2` 下的并持输出语义
- `single_symbol` fallback 在“缺一个槽位”时的 partial fill
- `etf_beta_selected_cap`
- `etf_beta_fallback_active`
- `etf_beta_under_deploy_reason_codes`

### 2. Governor 输出 ETF V2 部署语义

核心文件：
- `backend/core/config/cn_a_governed_mainline.py`
- `backend/core/stage_pipeline/adapters/daily_accounting.py`
- `backend/api/backtest_v2/artifacts_finalize.py`

本轮新增：
- `target_exposure`
- `min_deployable_exposure`
- `fallback_allowed`
- `under_deploy_reason_codes`
- `target_selected_count`

这些字段已进入：
- `portfolio_daily.csv`
- `run_meta.json`
- `audit.json`
- ETF sleeve summary / governed snapshot

### 3. Research audit 不再只看收益和路径

核心文件：
- `backend/core/audit/research_audit.py`

本轮新增 ETF 部署质量证据：
- 全窗口平均实际暴露
- 有持仓日平均实际暴露
- 持仓天数
- fallback 买入次数 / 天数
- under-deploy 原因统计
- `deployment_assessment`

### 4. V2 study 入口

新增 study：
- `research/studies/etf/cn_etf_beta_stabilizer_v2.study.yaml`

四组最小对照：
- `V2_CASH_1`
- `V2_CASH_2`
- `V2_BOND_1`
- `V2_BOND_2`

## AB Result

研究窗口：
- `2016-11-04 ~ 2026-03-24`

结果汇总：
- `outputs/ops/build_cn_etf_beta_stabilizer_v2_20260325/variant_compare.csv`
- `outputs/ops/build_cn_etf_beta_stabilizer_v2_20260325/summary.json`

对照组：
- `DM_BASIC_CASH_MA120`
- experiment: `exp_20260325_080101517_ee5a`

V2 四组：
- `V2_CASH_1`: `exp_20260325_085139737_90ff`
- `V2_CASH_2`: `exp_20260325_085145207_f167`
- `V2_BOND_1`: `exp_20260325_085150459_0ea0`
- `V2_BOND_2`: `exp_20260325_085155606_8d66`

关键结论：

1. `max_selected_symbols = 2` 明显抬升了 ETF 实际暴露。
   - control 平均实际暴露约 `5.31%`
   - `V2_CASH_2` 平均实际暴露约 `10.66%`
   - `V2_BOND_2` 平均实际暴露约 `10.80%`

2. `511010` fallback 比 `cash fallback` 略好。
   - `V2_BOND_2` 是本轮最合理的 beta stabilizer 候选
   - 但收益仍接近持平

3. ETF 收益弱不只是部署不足导致。
   - 部署改善后，收益仍未显著转正
   - 说明问题同时来自：
     - 过去部署过轻
     - ETF 候选和规则族本身贡献有限

## Recommendation

当前建议：
- 保留 `V2_BOND_2` 作为下一轮候选
- **不建议**现在就把 ETF sleeve 升格为正式收益主线

更准确地说：
- ETF V2 证明了“部署不足”确实是问题的一部分
- 但它还没有证明“只要部署上来，ETF 就能成为强收益层”

## Verification

已通过：

```bash
pytest tests/unit/test_cn_etf_beta_signal_provider.py tests/unit/test_research_audit_contract.py tests/unit/test_artifacts_finalize_regime_meta.py tests/unit/test_bridge_adapter_accounting.py tests/unit/test_semantic_config_compiler.py -q
```

以及：

```bash
docker exec backtest-v2-standalone python -m backend.cli study_run etf/cn_etf_beta_stabilizer_v2
openspec validate build-cn-etf-beta-stabilizer-v2 --type change --strict
```

## Rollback

如果回退这轮实现，优先撤回：

- `backend/core/engine_vector/cn_etf_beta_signal_provider.py`
- `backend/core/config/cn_a_governed_mainline.py`
- `backend/core/stage_pipeline/adapters/daily_accounting.py`
- `backend/core/audit/research_audit.py`
- `backend/api/backtest_v2/artifacts_finalize.py`
- `backend/api/backtest_v2/semantic_config_schema.py`
- `research/studies/etf/cn_etf_beta_stabilizer_v2.study.yaml`

如果只回退研究入口，不回退实现：

- 删除 `research/studies/etf/cn_etf_beta_stabilizer_v2.study.yaml`
- 忽略 `outputs/ops/build_cn_etf_beta_stabilizer_v2_20260325`

## Not Recommended

本轮明确不建议直接推进：

- 继续把 `510500 / 512100 / 512890` 放回 ETF V2 主研究线
- 继续把 ETF 解释成“收益主驱动”而不是 beta 稳定器
- 只看 CAGR，不看实际部署质量与 under-deploy 原因
