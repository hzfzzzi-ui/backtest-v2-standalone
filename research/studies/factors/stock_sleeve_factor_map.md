# A股 Stock Sleeve 全量因子图

## 1. 结论

截至 `2026-04-26`，当前 A 股 `stock sleeve` 已经具备一套相对完整的 factor research 结构，但它不是“所有 runtime 逻辑都已经因子化”。

更准确地说：

- 已有 `10` 个正式 stock-side factor families
- 已有 `42` 个可直接作为叶子因子研究的 `factor_id`
- 若把 `final_score_composition` 里的组合投影层一起算上，总计 `45` 个唯一 `factor_id`
- 其中仍有一批 **runtime / policy / execution** 逻辑没有也不应该被直接当成单因子

因此，当前正确理解应是：

- **研究面** 基本已经铺成体系
- **正式主线 runtime** 仍然包含一部分尚未 factorized 的边界逻辑

## 2. 统计口径

### 2.1 正式 stock-side factor families

1. `stock_alpha`
2. `moneyflow`
3. `positive_quality`
4. `industry_second_stage`
5. `negative_conditional_context`
6. `risk_gate`
7. `execution_pressure`
8. `exit_fragility`
9. `stock_lifecycle_fragility`
10. `final_score_composition`

### 2.2 数量

- 叶子因子总数：`42`
- 含投影/组合层的唯一 `factor_id` 总数：`45`

### 2.3 三个“只在组合层里出现”的投影项

这三项属于组合解释层，不应和叶子因子混为一谈：

- `final_score`
- `residual_strength_score`
- `sector_strength_score`

## 3. Family 到 Runtime 层的映射

| Runtime 层 | Family | 角色 |
|---|---|---|
| 入场 alpha | `stock_alpha` | 选股 / 排序基础信号 |
| 资金流上下文 | `moneyflow` | 中周期资金流上下文 |
| 正向质量增强 | `positive_quality` | quality/突破质量增强 |
| 行业二阶段 | `industry_second_stage` | 行业层二阶段增强 |
| 负向条件上下文 | `negative_conditional_context` | 拥挤/高位/事件条件风险 |
| 风险门 | `risk_gate` | 直接 veto / gate 风险 |
| 执行压力 | `execution_pressure` | 候选到部署之间的执行压力 |
| 退出脆弱性 | `exit_fragility` | 突破失败类退出前脆弱性 |
| 持有期脆弱性 | `stock_lifecycle_fragility` | 持有生命周期脆弱性 |
| 组合解释层 | `final_score_composition` | 当前正式排序分的组成解释 |

## 4. 全量叶子因子清单

### 4.1 `stock_alpha`

来源：

- [stock_alpha_factor_catalog.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/research/stock_alpha_factor_catalog.py)
- [stock_alpha_factor_real_mainline_s1.study.yaml](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/research/studies/factors/stock_alpha_factor_real_mainline_s1.study.yaml)

因子：

- `breakout_distance`
- `residual_strength`
- `trend_quality`
- `volatility_penalty`
- `liquidity_quality`

### 4.2 `moneyflow`

来源：

- [moneyflow_factor_catalog.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/research/moneyflow_factor_catalog.py)
- [moneyflow_factor_real_mainline_s1.study.yaml](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/research/studies/factors/moneyflow_factor_real_mainline_s1.study.yaml)

因子：

- `monthly_divergence_rate`

### 4.3 `positive_quality`

来源：

- [positive_quality_factor_catalog.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/research/positive_quality_factor_catalog.py)
- [positive_quality_factor_real_mainline_s1.study.yaml](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/research/studies/factors/positive_quality_factor_real_mainline_s1.study.yaml)

因子：

- `volume_price_quality_score`
- `breakout_quality_score`

### 4.4 `industry_second_stage`

来源：

- [industry_second_stage_factor_catalog.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/research/industry_second_stage_factor_catalog.py)
- [industry_second_stage_factor_real_mainline_s1.study.yaml](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/research/studies/factors/industry_second_stage_factor_real_mainline_s1.study.yaml)

因子：

- `industry_second_stage_score`
- `industry_second_stage_not_hot_score`
- `industry_second_stage_uncrowded_score`
- `industry_second_stage_breadth_timing_score`
- `industry_second_stage_persistence_10d`

### 4.5 `negative_conditional_context`

来源：

- [negative_conditional_context_factor_catalog.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/research/negative_conditional_context_factor_catalog.py)
- [negative_conditional_context_real_mainline_s1.study.yaml](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/research/studies/factors/negative_conditional_context_real_mainline_s1.study.yaml)

因子：

- `conditional_tiebreak_score`
- `conditional_factor_leader_score`
- `conditional_institution_proxy_score`
- `conditional_crowding_score`
- `conditional_recent_limit_hit_3d`
- `conditional_near_limit_up`

### 4.6 `risk_gate`

来源：

- [risk_gate_factor_catalog.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/research/risk_gate_factor_catalog.py)
- [risk_gate_factor_real_mainline_s1.study.yaml](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/research/studies/factors/risk_gate_factor_real_mainline_s1.study.yaml)

因子：

- `benchmark_regime_off_risk`
- `strong_risk_on_absence_risk`
- `regime_blocked_breakout_risk`
- `breakout_quality_fail_risk`
- `breakout_quality_gate_shortfall_risk`
- `bull_quality_residual_shortfall_risk`
- `bull_quality_margin_shortfall_risk`

### 4.7 `execution_pressure`

来源：

- [execution_pressure_factor_catalog.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/research/execution_pressure_factor_catalog.py)
- [execution_pressure_factor_real_mainline_s1.study.yaml](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/research/studies/factors/execution_pressure_factor_real_mainline_s1.study.yaml)

因子：

- `slot_overhang_pressure`
- `cash_lot_pressure`
- `budget_reject_pressure`
- `deployment_gap_pressure`
- `underexposure_pressure`
- `cash_drag_pressure`

### 4.8 `exit_fragility`

来源：

- [exit_fragility_factor_catalog.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/research/exit_fragility_factor_catalog.py)
- [exit_fragility_factor_real_mainline_s1.study.yaml](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/research/studies/factors/exit_fragility_factor_real_mainline_s1.study.yaml)

因子：

- `breakout_margin_raw`
- `breakout_margin_score`
- `breakout_fade_raw`
- `breakout_open_gap_raw`
- `breakout_quality_score`

### 4.9 `stock_lifecycle_fragility`

来源：

- [stock_lifecycle_fragility_catalog.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/research/stock_lifecycle_fragility_catalog.py)
- [stock_lifecycle_fragility_real_mainline_s1.study.yaml](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/research/studies/factors/stock_lifecycle_fragility_real_mainline_s1.study.yaml)

因子：

- `early_fade_risk`
- `weak_carry_risk`
- `break_floor_risk`
- `pre_profit_failure_context_risk`
- `low10_exit_context_risk`
- `risk_off_exit_context_risk`

## 5. 组合解释层 `final_score_composition`

来源：

- [final_score_composition_catalog.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/research/final_score_composition_catalog.py)
- [final_score_composition_real_mainline_s1.study.yaml](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/research/studies/factors/final_score_composition_real_mainline_s1.study.yaml)

这层不是新的叶子因子池，而是**当前正式排序总分的投影解释层**。

包含：

- `final_score`
- `residual_strength_score`
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

其中重复映射项说明：

- `volume_price_quality_score`：同时属于 `positive_quality`
- `breakout_quality_score`：同时属于 `positive_quality` 与 `exit_fragility`
- `breakout_margin_score`：同时属于 `exit_fragility`
- `conditional_*`：同时属于 `negative_conditional_context`
- `industry_second_stage_*`：同时属于 `industry_second_stage`

因此 `final_score_composition` 应理解为：

- **解释层**
- **组合层**
- **投影层**

而不是新增一个独立叶子因子 family。

## 6. 当前仍未完全 factorized 的 stock sleeve 逻辑

以下逻辑仍然存在于 runtime / policy / execution 层，不应误判为“已经全量因子化”。

### 6.1 Universe / entry boundary

来源：

- [mainline_breakout_runtime_context.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/research/mainline_breakout_runtime_context.py)

仍属 runtime 逻辑的内容包括：

- `min_price`
- `min_list_days`
- `min_avg_turnover_20d`
- `min_avg_turnover_rate_20d`
- `exclude_star_market`
- `dynamic_all_a_entry`

这些是 **股票池/可交易池边界**，不是普通单因子。

### 6.2 Regime / state gating

仍属 runtime 或账户层上下文的内容包括：

- `risk_on_arr`
- `strong_risk_on_arr`
- `effective_state_5_arr`
- benchmark regime engine

它们可以派生风险或上下文研究项，但本体是 **状态机 / 门控逻辑**。

### 6.3 Candidate boundary / execution planning

仍属执行核逻辑的内容包括：

- slot cap
- cash lot affordability
- sleeve budget reject
- deployment gap
- rotation replace
- order planning / fill / accounting

这里已经部分映射成 `execution_pressure`，但那只是**研究镜像**，不是把执行核本身变成因子。

### 6.4 Exit rule runtime

当前已经 factorized 的只是 fragility/context 层：

- `exit_fragility`
- `stock_lifecycle_fragility`

但真正的退出动作本身仍然是 runtime 合同，例如：

- pre-profit breakout failure exit
- low10 exit
- risk-off exit
- ATR stop
- MA20 exit

也就是说：

- **exit 风险上下文** 已经可因子化研究
- **exit 动作本体** 仍然是 runtime 逻辑

## 7. 当前最合理的理解

当前 A 股 `stock sleeve` 可以按三层理解：

### 7.1 叶子因子层

就是上面 `42` 个可直接做单因子分析的对象。

### 7.2 组合解释层

就是 `final_score_composition`。

它负责回答：

- 正式主线当前到底是哪些分数组成的
- 哪些已研究 family 在 runtime 里被重复消费

### 7.3 残余 runtime 层

包括：

- universe 边界
- regime/state gate
- candidate boundary
- sizing / slot / cash
- exit 动作

这部分还没有也不应该被粗暴地当成普通单因子。

## 8. 下一步建议

如果后续要继续推进“stock sleeve 全量因子化”，推荐顺序是：

1. 先把 `final_score_composition` 里的 `residual_strength_score / sector_strength_score` 再向下追到更明确的 leaf map
2. 再决定 universe / regime / exit 动作里哪些适合继续抽成 research-only factor mirrors
3. 不要把 execution / policy / action 本体直接伪装成单因子

一句话收口：

**当前 A 股 stock sleeve 已经有一份可工作的全量 factor map，但它覆盖的是“研究可拆解面”，不是“整个 runtime 已经 100% 因子化”。**
