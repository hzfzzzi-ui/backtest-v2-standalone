# A股 Stock Sleeve 当前 Live Baseline 因子图

## 1. 结论

截至 `2026-04-26`，当前正式 `baseline_V10_1` 的 A 股 `stock sleeve`，如果只看**真正已启用并参与 live 排序总分的因子**，结论很窄：

- 当前 live 排序主因子实质上只有 `residual_strength_score`
- `monthly_divergence_rate` 当前**没有**接入 `baseline_V10_1` 的正式 runtime
- `sector_strength_score`、`volume_price_quality_score`、`industry_second_stage_*`、`conditional_*` 当前大多是
  - 已实现的研究镜像
  - 或 provider 里会计算、会出现在 meta 里
  - 但**没有进入当前 live baseline 的 final_score 真正排序链**

因此，当前应把两件事严格分开：

- **live baseline 已启用因子**
- **研究面已存在但尚未接入的候选因子**

## 2. 事实链

### 2.1 baseline 语义配置事实

见 [config.json](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/baselines/baseline_V10_1/config.json)：

- `signal_generation.ranking.score_source_mode = residual_only`
- `signal_generation.ranking.residual_window = 40`
- `signal_generation.ranking.residual_benchmark_weight = 0.0`
- `signal_generation.ranking.residual_industry_weight = 1.0`
- 没有显式配置：
  - `residual_refine_mode`
  - `residual_refine_weight`
  - `enable_sector_quality_ranking`
  - `moneyflow_overlay`
  - `signal_generation.modules[*]=moneyflow_monthly`

### 2.2 编译层事实

见 [runner_config_risk_exit.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/api/backtest_v2/runner_config_risk_exit.py)：

- `score_source_mode = residual_only` 会编译成：
  - `ranking_mode = residual_only`
  - `enable_residual_ranking = true`
  - `enable_sector_quality_ranking = false`

这一步很关键，因为它决定了 live runtime 到底有没有把 `sector/quality` 拼进 `final_score`。

### 2.3 runtime 计算事实

见 [breakout_provider_precompute.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/engine_vector/breakout_provider_precompute.py)：

- `residual_component` 默认来自 `provider._residual_strength_score`
- 只有在下面几种条件满足时，`residual_component` 才会被别的研究因子修正：
  - `residual_refine_mode == breakout_margin`
  - `residual_refine_mode == conditional_tiebreak`
  - `residual_refine_mode == industry_second_stage`
  - 且 `residual_refine_weight > 0`
- 当前 `baseline_V10_1` 没有打开这些条件

同一个文件里还有一条关键逻辑：

- 只有 `enable_sector_quality_ranking = true` 时
  - `sector_strength_score`
  - `volume_price_quality_score`
  才会进入 `score_components`

而当前 `residual_only` 会把它关掉。

### 2.4 final_score 真相

同样见 [breakout_provider_precompute.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/engine_vector/breakout_provider_precompute.py)：

- 当前 `baseline_V10_1` 下：
  - `enable_residual_ranking = true`
  - `enable_sector_quality_ranking = false`
  - `residual_refine_mode = off`

所以当前 `provider._final_score` 的真实含义是：

- `final_score = residual_strength_score`

不是：

- `residual + sector + quality`
- 也不是 `provider_final`
- 更不是 `moneyflow + residual`

## 3. 当前 live baseline 已启用的 stock-side 因子

### 3.1 直接参与 live 排序总分

- `residual_strength_score`

这是当前唯一明确参与 `final_score` 的叶子因子。

### 3.2 当前 active 的 runtime gate / policy，但不应误叫“排序因子”

这些是 live baseline 真正启用的主线行为约束，但它们不等于研究层叶子因子：

- `benchmark_regime`
- `market_filter`
- `v2_trend_ok`
- `entry_above_slow_ma / slow_ma_slope` 这类 entry gate
- `max_positions / risk_budget / cost_model`
- `ATR stop / low10 exit / risk_off_exit`

它们会强烈影响结果，但不属于“当前已启用排序主因子”。

## 4. 当前会计算、会出现在 meta，但没有接入 live 排序总分的成分

见 [breakout_provider_day_signals.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/engine_vector/breakout_provider_day_signals.py) 和
[final_score_composition_catalog.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/research/final_score_composition_catalog.py)：

- `sector_strength_score`
- `volume_price_quality_score`
- `breakout_quality_score`
- `breakout_margin_score`
- `conditional_tiebreak_score`
- `conditional_factor_leader_score`
- `conditional_institution_proxy_score`
- `conditional_crowding_score`
- `industry_second_stage_score`
- `industry_second_stage_not_hot_score`
- `industry_second_stage_uncrowded_score`
- `industry_second_stage_breadth_timing_score`
- `industry_second_stage_persistence_10d`

这些成分当前的状态应理解为：

- **provider 已实现**
- **研究 surface 已存在**
- **day signal meta 里可见**
- **但 baseline_V10_1 并未把它们接入 final_score live 排序**

## 5. 关于 `MF Rank` 的纠偏

`baseline_V10_1/config.json` 里确实有：

- `signal_composition.modules[].name = MF Rank`

但这不能直接推导成：

- `monthly_divergence_rate` 已经接入当前 live baseline

原因有两个：

1. 当前这条 A 股主线不是 `signal_generation.modules` 的 multi-alpha 主路径  
   见 [execution_overrides.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/api/backtest_v2/execution_overrides.py)，
   multi-alpha payload 只有在 `signal_generation.modules` 是列表时才会正式编译。

2. 当前 baseline 配置里没有：
   - `moneyflow_monthly`
   - `moneyflow_overlay`
   - `score_field = monthly_divergence_rate`

所以 `MF Rank` 当前更像：

- 历史语义标签
- 或 UI/语义层残留命名

而不是当前 runtime 中已经启用的 `moneyflow` 因子事实。

## 6. 当前最准确的 live factor map

### 6.1 live 排序因子

- `residual_strength_score`

### 6.2 live 行为约束

- regime / market filter
- breakout entry gate
- position risk / budget
- exit rules

### 6.3 研究候选但未接入 live 排序

- `monthly_divergence_rate`
- `volume_price_quality_score`
- `breakout_quality_score`
- `industry_second_stage_*`
- `conditional_*`
- `sector_strength_score`

## 7. 一句话收口

当前 `baseline_V10_1` 的 A 股 `stock sleeve`，**不是一个多因子 live 排序系统**。  
它更准确地说是：

- **一个以 `residual_strength_score` 为唯一 live 排序主因子**
- **叠加 regime / entry / risk / exit 约束**
- **周围包着一圈已经实现但尚未正式接入的研究候选因子**
