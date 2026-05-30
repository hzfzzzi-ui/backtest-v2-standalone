# `pams_ohlcv_daily_v2_runtime` Contract

## 定位

`pams_ohlcv_daily_v2_runtime` 是 `pams_ohlcv_daily_v2` 之上的过渡期 runtime compatibility 视图。

它的职责是托底当前仍依赖 runtime compatibility 的旧运行链，不代表数据库长期正式分层。

- `canonical` 目标：最大化真实信息保留、来源透明、异常显式
- `runtime` 目标：为 `V10.1` 等正式 baseline 提供更稳定、可控、可审计的消费集合

`runtime` 不是新的真值表，也不替代 canonical；长期应尽量被 `canonical_market` 或统一数据访问层吸收。

## 当前规则

当前 view 仅保留满足以下条件的 canonical 记录：
- `row_status IN ('traded', 'suspended_confirmed')`
- `pre_close_confidence >= 1`
- `adj_factor_confidence >= 1`
- `turnover_rate_confidence >= 1 OR is_suspended = true`

这意味着：
- `source_unresolved` 不进入 runtime
- `delist_tail_confirmed` 不进入 runtime，包括显式官方 override 命中的 terminal 行
- `synthetic_gap_fill` 不进入 runtime
- 低可信 `pre_close` / `adj_factor` 记录被排除
- 停牌确认行允许 `turnover_rate = 0`

## 数据角色

当前过渡实现中，运行时配置仍允许显式选择：
- `v1`
- `v2_canonical`
- `v2_runtime`

对应关系：
- `v1` -> `pams_ohlcv_daily`
- `v2_canonical` -> `pams_ohlcv_daily_v2`
- `v2_runtime` -> `pams_ohlcv_daily_v2_runtime`

但正式方向已经收口为：

- 新配置不应继续以 `v1` 或 `v2_runtime` 作为正式上层入口
- `v2_runtime` 只允许旧 baseline 迁移期使用
- `data_role` 长期应被更稳定的市场数据访问合同替代，而不是继续作为正式用户接口保留

## 审计要求

`run_meta.json` 与 `resolved_config.json` 必须能回显：
- `data_role`
- `stocks_table`
- `stocks_mapping_table`

否则不得视为 runtime compat 已可审计。
