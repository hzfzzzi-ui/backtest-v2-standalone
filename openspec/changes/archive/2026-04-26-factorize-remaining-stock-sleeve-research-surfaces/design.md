# Design

## Boundaries

本 change 继续完成股票腿剩余研究拆分，但保持：

- `RESEARCH_ONLY`
- 基线锚定
- 不动正式 runtime

## Surfaces

### 1. Negative Conditional Context

来源于主线 `final_score` 的负向条件上下文族：

- `conditional_tiebreak_score`
- `conditional_factor_leader_score`
- `conditional_institution_proxy_score`
- `conditional_crowding_score`
- `conditional_recent_limit_hit_3d`
- `conditional_near_limit_up`

角色定义：

- 条件 / veto / context
- 研究口径采用 fragility-style bucket analysis

### 2. Industry Second Stage

来源于主线行业二阶段族：

- `industry_second_stage_score`
- `industry_second_stage_not_hot_score`
- `industry_second_stage_uncrowded_score`
- `industry_second_stage_breadth_timing_score`
- `industry_second_stage_persistence_10d`

角色定义：

- rank / context 混合
- 研究口径先按 rank surface 处理

### 3. Execution Pressure

来源于 stock sleeve `portfolio_daily.csv`：

- `buy_candidate_count`
- `after_slot_filter_count`
- `after_cash_lot_count`
- `selected_count`
- `buy_slots_calculated`
- `sleeve_budget_reject_count`
- `gross_exposure`
- `cash / nav`

构造 account-level daily pressure：

- `slot_overhang_pressure`
- `cash_lot_pressure`
- `budget_reject_pressure`
- `deployment_gap_pressure`
- `underexposure_pressure`
- `cash_drag_pressure`

角色定义：

- account-level context / veto
- 研究口径使用时间序列 forward-return bucket analysis

## Outputs

每条线都输出：

- catalog
- snapshot
- factor score snapshot
- machine analysis
- human summary

## Real Studies

统一使用：

- baseline anchor: `baseline_V10.1`
- stock sleeve runtime carrier: `exp_20260409_052948616_a4c5`
- windows:
  - `1217`
  - `1222`
  - `1226`
