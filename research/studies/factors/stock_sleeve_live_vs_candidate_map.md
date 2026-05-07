# A股 Stock Sleeve 当前 Live 因子与研究候选因子对照表

## 1. 结论

截至 `2026-04-26`，当前正式 `baseline_V10_1` 的 A股 `stock sleeve`，应严格拆成两层来看：

- **当前 live baseline 已启用因子**
- **研究面已实现但尚未接入 live 排序的候选因子**

当前 live baseline 的核心事实很窄：

- 真正参与当前 live 排序总分的主因子，本质上只有 `residual_strength_score`
- 其余很多常被讨论的因子，例如 `monthly_divergence_rate`、`volume_price_quality_score`、`industry_second_stage_*`、`conditional_*`，当前都更接近**研究候选**，不是正式 live 排序链的一部分
- 因此，当前 A股主线不是“多因子同时 live 驱动”，而是**单主因子排序 + 一组 runtime gate / 风险约束 / 执行约束**

## 2. 总体对照

| 层级 | 当前状态 | 说明 |
|---|---|---|
| Live 排序主因子 | 已启用 | `residual_strength_score` |
| Live 运行约束 | 已启用 | benchmark / regime / breakout entry gate / position risk / exits |
| 质量增强因子 | 已实现但未接入 live 排序 | `volume_price_quality_score`、`breakout_quality_score` |
| 行业二阶段因子 | 已实现但未接入 live 排序 | `industry_second_stage_*` |
| 资金流因子 | 已实现但未接入 live 排序 | `monthly_divergence_rate` |
| 条件上下文因子 | 已实现但未接入 live 排序 | `conditional_*` |
| 执行压力因子 | 已实现但未接入 live 排序 | `*_pressure` |
| 脆弱性因子 | 已实现但未接入 live 排序 | `*_fragility`、`*_risk` |
| 风险门因子 | 已实现但未接入 live 排序 | `*_gate_*` |

## 3. 当前 Live Baseline 已启用部分

### 3.1 排序主因子

当前正式 `baseline_V10_1` 下，真正进入 `final_score` 的主因子是：

- `residual_strength_score`

这条事实来自三层共同确认：

- [outputs/baselines/baseline_V10_1/config.json](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/baselines/baseline_V10_1/config.json)
- [runner_config_risk_exit.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/api/backtest_v2/runner_config_risk_exit.py)
- [breakout_provider_precompute.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/engine_vector/breakout_provider_precompute.py)

在当前配置下：

- `score_source_mode = residual_only`
- `enable_residual_ranking = true`
- `enable_sector_quality_ranking = false`
- `residual_refine_mode = off`

所以当前 live 含义就是：

- `final_score = residual_strength_score`

### 3.2 当前 live runtime 约束

虽然不是“排序因子”，但当前 live 主线真实在用的还有一组 runtime 约束：

- benchmark / regime 约束
- market filter / breakout entry 条件
- position risk 控制
- 持仓与退出逻辑
- stage pipeline 的候选、下单、成交、记账约束

这些属于**正式主线行为的一部分**，但不应混同为“单因子”。

## 4. 已实现但未接入 Live 排序的研究候选

### 4.1 资金流候选

- `monthly_divergence_rate`

说明：

- 当前已存在独立 study 与 surface
- 研究上表现较强
- 但当前 `baseline_V10_1` 没有把它正式接进 live 排序链

### 4.2 正向质量候选

- `volume_price_quality_score`
- `breakout_quality_score`
- `breakout_margin_score`

说明：

- 当前可以计算、可以研究、可出现在 factor matrix
- 但在当前 `residual_only` 口径下，没有进入 live `final_score`

### 4.3 行业二阶段候选

- `industry_second_stage_score`
- `industry_second_stage_not_hot_score`
- `industry_second_stage_uncrowded_score`
- `industry_second_stage_breadth_timing_score`
- `industry_second_stage_persistence_10d`

说明：

- 这一组已经形成较完整研究面
- 当前仍属候选增强层，不是 baseline 已启用主因子

### 4.4 条件上下文候选

- `conditional_tiebreak_score`
- `conditional_factor_leader_score`
- `conditional_institution_proxy_score`
- `conditional_crowding_score`
- 以及一组 `conditional_*` 负向条件因子

说明：

- 这些因子目前更像“排序修正 / 风险上下文”
- 已有研究价值，但不等于已经接入当前 live baseline

### 4.5 风险门、执行压力与脆弱性候选

- `breakout_quality_gate_shortfall_risk`
- `deployment_gap_pressure`
- `cash_drag_pressure`
- `underexposure_pressure`
- `early_fade_risk`
- `weak_carry_risk`
- `breakout_fade_raw`

说明：

- 这些更适合做 veto、pressure、fragility 研究
- 当前不是正式 live 排序链的一部分

## 5. Family 级对照

| 因子族 | 当前是否进入 live 排序 | 当前角色 |
|---|---|---|
| `stock_alpha` | 部分进入 | 只有 `residual_strength_score` 真正 live |
| `moneyflow` | 否 | 研究候选 |
| `positive_quality` | 否 | 研究候选 |
| `industry_second_stage` | 否 | 研究候选 |
| `negative_conditional_context` | 否 | 研究候选 |
| `risk_gate` | 否 | 研究候选 / veto 镜像 |
| `execution_pressure` | 否 | 研究候选 / pressure 镜像 |
| `exit_fragility` | 否 | 研究候选 / exit 镜像 |
| `stock_lifecycle_fragility` | 否 | 研究候选 / lifecycle 镜像 |
| `final_score_composition` | 部分进入 | 当前主要是解释层，不是独立 live 因子族 |

## 6. 当前应如何使用这张表

正确用法：

- 解释当前正式 baseline：先看 `residual_strength_score` 和 runtime gate
- 排下一轮研究优先级：再看 `moneyflow / quality / industry_second_stage / pressure / fragility`
- 做单因子矩阵：明确它是**研究优先级矩阵**，不是“当前 live baseline 因子强弱表”

错误用法：

- 把 `monthly_divergence_rate` 当成当前 baseline 已启用因子
- 把 `conditional_*` 或 `industry_second_stage_*` 当成当前正式排序主因子
- 把研究候选矩阵直接当作 live baseline 归因表

## 7. 一句话总结

当前 `baseline_V10_1` 的 A股 `stock sleeve`，本质上是：

- **`residual_strength_score` 单主因子 live 排序**
- **其他大量因子仍处于研究候选层**
- **runtime gate / 风险约束 / 执行约束共同塑造最终行为**
