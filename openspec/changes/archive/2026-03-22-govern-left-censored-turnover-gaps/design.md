## Context

`pre_close_imputed_zero` 的左截断治理完成后，`2012-2017` hard gate 剩余的有效 critical 只剩 `756` 行。实库核查表明，这 `756` 行全部来自：

- `sz000156` `191`
- `sz000622` `268`
- `sz000805` `297`

共同特征是：

- `row_status ∈ {synthetic_gap_fill, delist_tail_confirmed}`
- `turnover_rate_source = imputed_zero`
- `source_daily_basic_present = false`
- `float_share/free_share = null`
- 同一 `symbol/trade_date` 已有 `pre_close_imputed_zero + left_censored_anchor_gap`

扩到 `2007-2026`，同类 `SH/SZ` 左截断非 traded 样本共 `9853` 行。它们与刚完成的 `pre_close` 左截断治理是同一批样本。

## Goals / Non-Goals

**Goals:**

- 给这批 `turnover_rate_imputed_zero` 一个显式可审计的左截断 cause class。
- 让 canonical gate 将其计入 `known_source_gap_rows`，不再继续作为有效 critical。
- 保持 runtime 不放宽。

**Non-Goals:**

- 不补新的 `daily_basic` 或股本外部源。
- 不处理 `source_unresolved` 的真无源 `turnover_rate`。
- 不修改 runtime 的默认排除门槛。

## Decisions

### 1. 只对非 traded 且已命中左截断 `pre_close` 的样本生效

`left_censored_turnover_gap` 只允许命中 `synthetic_gap_fill / suspended_confirmed / delist_tail_confirmed`，并要求当前 `pre_close_source = imputed_zero`。这样规则与上一刀的 `pre_close` 左截断治理对齐，不会吞掉 traded 行或中段构建回归。

不选择“所有 SH/SZ fallback_available 都并入 known gap”，因为那会把真构建问题一起洗掉。

### 2. runtime 不新增特殊 reason

这批样本已经被 `row_status_synthetic_gap_fill / row_status_delist_tail_confirmed` 排除，runtime 不需要再加一条新的排除 reason。

不选择新增 runtime reason，是为了避免把 canonical 解释修正误当成 runtime 行为变化。

## Risks / Trade-offs

- [风险] 如果条件写得过宽，会吞掉未来出现的非 traded 中段回归。
  - 缓解：强制要求 `pre_close_source = imputed_zero`，并用测试锁住 `source_unresolved` 不并入。
- [风险] `2012-2017` 清零后，`2007-2026` advisory 仍会剩一批真无源和 mapping 尾巴。
  - 缓解：这次 change 只承诺清左截断已知源缺口，不承诺清 advisory 全周期 backlog。
