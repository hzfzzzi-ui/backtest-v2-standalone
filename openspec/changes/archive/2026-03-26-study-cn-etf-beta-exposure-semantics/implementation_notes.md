## Summary

`study-cn-etf-beta-exposure-semantics` 已完成实现与研究验证。本轮没有改 ETF 候选池，只研究 `target_exposure / min_deployable_exposure / deployability` 语义对 ETF sleeve 部署质量与结果的影响。

研究定义：
- [cn_etf_beta_exposure_semantics.study.yaml](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/research/studies/etf/cn_etf_beta_exposure_semantics.study.yaml)

正式产物：
- [variant_compare.csv](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/ops/study_cn_etf_beta_exposure_semantics_20260326/variant_compare.csv)
- [summary.json](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/ops/study_cn_etf_beta_exposure_semantics_20260326/summary.json)

对应实验：
- `EXP_CTRL_BOND_2`: [exp_20260325_215913282_7f44](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/experiments/exp_20260325_215913282_7f44)
- `EXP_FIXED_35_15`: [exp_20260325_215919642_d715](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/experiments/exp_20260325_215919642_d715)
- `EXP_STATE_SEGMENTED`: [exp_20260325_215925313_5663](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/experiments/exp_20260325_215925313_5663)

## What Changed

本轮实现围绕 5 个方面：

1. 为 `cn_etf_beta` 新增显式暴露语义配置：
- `target_exposure_by_state_5`
- `min_deployable_exposure_by_state_5`

2. 为 Governor / 日级产物输出新增 ETF 部署证据：
- `etf_target_exposure`
- `etf_min_deployable_exposure`
- `etf_actual_exposure`
- `etf_actual_risk_exposure`
- `etf_actual_fallback_exposure`
- `etf_actual_other_exposure`
- `etf_deployability_gap`

3. 为 ETF provider 补充 target/min exposure 诊断、per-symbol target exposure 与 under-deploy reason code。

4. 扩展 research audit，使 `audit.research_audit.gates.etf_beta_sleeve` 正式输出 ETF 部署质量指标。

5. 新建最小 AB study，对比：
- 控制组：`EXP_CTRL_BOND_2`
- 固定更高暴露：`EXP_FIXED_35_15`
- 5 状态分段暴露：`EXP_STATE_SEGMENTED`

## Findings

### 1. 部署不足确实存在，但不是唯一问题

事实：
- 控制组 `EXP_CTRL_BOND_2`
  - 平均目标暴露：`20.0%`
  - 平均实际暴露：`10.80%`
  - 平均 deployability gap：`13.07%`
- 固定更高暴露 `EXP_FIXED_35_15`
  - 平均目标暴露：`35.0%`
  - 平均实际暴露：`18.66%`
  - 平均 deployability gap：`22.88%`
- 分段暴露 `EXP_STATE_SEGMENTED`
  - 平均目标暴露：`21.04%`
  - 平均实际暴露：`21.23%`
  - 平均 deployability gap：`7.51%`

判断：
- `EXP_STATE_SEGMENTED` 明显改善了部署质量。
- `EXP_FIXED_35_15` 也抬高了平均实际暴露。
- 所以“ETF 结果弱完全只是部署不足”这个假设不成立。

### 2. 把暴露抬起来后，收益没有改善，回撤反而更差

事实：
- `EXP_CTRL_BOND_2`
  - `CAGR -0.05%`
  - `MaxDD -10.45%`
- `EXP_FIXED_35_15`
  - `CAGR -0.15%`
  - `MaxDD -17.61%`
- `EXP_STATE_SEGMENTED`
  - `CAGR -0.19%`
  - `MaxDD -19.88%`

判断：
- 暴露语义抬高后，收益没有被救回来。
- 风险显著放大。
- 这说明当前 ETF sleeve 的弱点，不只是“仓位太低”。

### 3. under-deploy 的主因仍然集中在同一组结构原因

三组实验里最主要的 under-deploy reason family 都没有改变主排序：
- `ETF_BETA_SLOT_CAP_ZERO`
- `ETF_BETA_MIN_DEPLOYABLE_EXPOSURE_UNMET`
- `ETF_BETA_NO_ELIGIBLE_AFTER_ABSOLUTE_FILTER`
- `CANDIDATES_BELOW_BUDGET`
- `NO_SELECTED_ORDERS`

判断：
- 当前候选池与绝对过滤仍然是 ETF 部署受限的重要来源。
- 单独改暴露语义，不能绕开“可部署标的本身有限”这个事实。

### 4. fallback 不是主要拖累

事实：
- 三组实验的 `fallback_buy_count` 都只有 `7`
- 平均 fallback 暴露都在 `0.14% ~ 0.28%`

判断：
- 当前结果差，不是 `511010` fallback 把收益拖没了。
- `fallback` 更像次要修饰项，不是主解释项。

### 5. 损失拆解结论

参考风险篮子：`510050 + 510300` 等权买入持有价格年化约 `2.73%`。

控制组 `EXP_CTRL_BOND_2`：
- 预算上限损失约 `1.93 pct`
- 空仓/低仓损失约 `0.59 pct`
- fallback 对收益是小幅正贡献
- 过滤/切换/交易损失约 `0.46 pct`

固定更高暴露 `EXP_FIXED_35_15`：
- 预算上限损失下降到约 `1.41 pct`
- 但空仓/低仓损失扩大到约 `1.14 pct`
- 过滤/切换/交易损失扩大到约 `0.68 pct`

状态分段 `EXP_STATE_SEGMENTED`：
- 预算上限损失基本消失
- 但空仓/低仓损失扩大到约 `2.63 pct`
- 过滤/切换/交易损失扩大到约 `0.72 pct`

判断：
- 这轮研究已经证明：把 target exposure 做高、或把 5 状态映射做得更激进，不会自动带来更好的 ETF 收益。

## Formal Conclusion

正式结论：
- **不建议继续把“ETF 暴露语义”作为当前 ETF 主问题的第一优先级推进线。**
- 本轮更合理的处理方式是：
  - 保留新增的暴露证据链与审计字段
  - 不把 `EXP_FIXED_35_15` 和 `EXP_STATE_SEGMENTED` 升格为新的 ETF 正式默认语义
  - 后续如继续研究，应回到更上游的问题：
    - 候选池是否过弱
    - 绝对过滤是否过严
    - 是否应转向 total-return 口径研究

建议保留：
- 新增的 ETF 暴露字段
- deployability / under-deploy reason 审计
- 本轮 compare/summary 产物

不建议推进：
- 直接把 ETF target exposure 从 `20%` 抬到 `35%`
- 直接把分段暴露变成新的默认规则

## Verification

已通过：
- `pytest tests/unit/test_cn_etf_beta_signal_provider.py tests/unit/test_bridge_adapter_accounting.py tests/unit/test_research_audit_contract.py tests/unit/test_artifacts_finalize_regime_meta.py tests/unit/test_experiment_runner_daily_schema.py tests/unit/test_semantic_config_compiler.py -q`
- `docker exec backtest-v2-standalone python -m backend.cli study_run etf/cn_etf_beta_exposure_semantics`
- `openspec validate study-cn-etf-beta-exposure-semantics --type change --strict`

## Rollback

如果需要回退本轮实现，建议顺序如下：

1. 回退研究定义与研究产物依赖：
- [cn_etf_beta_exposure_semantics.study.yaml](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/research/studies/etf/cn_etf_beta_exposure_semantics.study.yaml)

2. 回退 ETF 暴露语义 contract / runtime 输出：
- [semantic_config_schema.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/api/backtest_v2/semantic_config_schema.py)
- [cn_a_governed_mainline.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/config/cn_a_governed_mainline.py)
- [daily_accounting.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/stage_pipeline/adapters/daily_accounting.py)
- [cn_etf_beta_signal_provider.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/engine_vector/cn_etf_beta_signal_provider.py)
- [portfolio_runtime.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/portfolio/portfolio_runtime.py)
- [experiment_runner.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/tools/experiment_runner.py)
- [artifacts_finalize.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/api/backtest_v2/artifacts_finalize.py)

3. 回退 ETF 审计扩展：
- [research_audit.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/audit/research_audit.py)

4. 回退单测：
- [test_cn_etf_beta_signal_provider.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/tests/unit/test_cn_etf_beta_signal_provider.py)
- [test_bridge_adapter_accounting.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/tests/unit/test_bridge_adapter_accounting.py)
- [test_research_audit_contract.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/tests/unit/test_research_audit_contract.py)
- [test_artifacts_finalize_regime_meta.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/tests/unit/test_artifacts_finalize_regime_meta.py)
- [test_experiment_runner_daily_schema.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/tests/unit/test_experiment_runner_daily_schema.py)
- [test_semantic_config_compiler.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/tests/unit/test_semantic_config_compiler.py)
