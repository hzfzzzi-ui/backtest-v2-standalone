# `V2` Exception Taxonomy

## 1. 目的

这份字典用于统一 `pams_ohlcv_daily_v2_exceptions` 的来源解释，避免不同脚本对同一异常给出不同语义。

异常解释至少拆成两层：
- `issue_type`：外层异常名称
- `cause_class`：来源解释分类

## 2. 来源解释分类

| cause_class | 含义 | 典型场景 |
|---|---|---|
| `missing_in_all_sources` | 主源、补源、审计源都无法给出有效观测 | `eligible_no_source` 且 `daily/suspend/basic` 全空 |
| `fallback_available` | 主源缺失，但补源或推导链可提供低可信值 | `turnover_rate` 缺主源但可由 `AkShare` 或公式补出 |
| `mapping_failure` | 证券映射、阶段归属或 lineage 规则不清，导致应有行或 symbol 对不上 | `BJ pre-2021-11-15` 历史映射污染 |
| `build_rule_rejected` | 原始源存在，但 build 规则未接纳或被显式丢弃 | raw 存在但 canonical 未落行 |
| `source_present_low_confidence_fill` | 有部分源可用，但最终字段只能通过低可信锚点或补值形成 | `pre_close_imputed_zero`、synthetic fill |

## 3. 关键 `issue_type` 对应关系

| issue_type | 默认 cause_class | 说明 |
|---|---|---|
| `eligible_no_source` | `missing_in_all_sources` / `mapping_failure` | 需结合市场阶段判断 |
| `turnover_rate_imputed_zero` | `fallback_available` / `missing_in_all_sources` | 如果 `AkShare` 或公式可补但未补，需归因修正 |
| `pre_close_imputed_zero` | `source_present_low_confidence_fill` | 早年锚点不足时常见 |
| `adj_factor_missing` | `missing_in_all_sources` / `source_present_low_confidence_fill` | 看是否有前值 carry |
| `raw_only_not_in_master` | `build_rule_rejected` / `mapping_failure` | raw 有行但 canonical 没写 |
| `daily_basic_missing` | `missing_in_all_sources` / `fallback_available` | 取决于补源可得性 |
| `moneyflow_missing` | `missing_in_all_sources` | 仅用于侧表，不作为主表阻塞 |

## 4. 使用规则

- 每条关键异常应至少能落到一个 `cause_class`
- `BJ pre-2021-11-15` 的 `eligible_no_source` 默认优先检查 `mapping_failure`
- `BJ post-2021-11-15` 的 `eligible_no_source` 默认优先检查 `missing_in_all_sources`
- 不能把所有 `eligible_no_source` 统一解释成“数据源失败”

## 5. 审计输出要求

质量审计至少应按以下维度聚合：
- `issue_type`
- `cause_class`
- `exchange/market_phase`
- `year`
- `symbol`

这样才能回答：
- 是源真的没有？
- 还是补源没接？
- 还是 `BJ` 历史映射没治理好？
