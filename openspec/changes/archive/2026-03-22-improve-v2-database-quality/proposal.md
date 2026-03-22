## Why

`pams_ohlcv_daily_v2` 已经完成全历史回填与审计，但当前仍未通过正式升格门禁：硬字段空值虽已压到 `0`，却仍存在大量 `eligible_no_source`、`turnover_rate_imputed_zero` 与 `pre_close_imputed_zero`。同时，`V10.1` 在 `v2` 上回归明显偏离 `v1`，说明当前 `v2` 还缺少一套把“canonical 真值底座”和“runtime 兼容消费”分开的正式治理方案。

## What Changes

- 建立 `v2` 的字段级与交易所级 source governance，明确 `Tushare`、`AkShare`、`巨潮资讯` 等主源、补源、审计源分工。
- 重构 `v2` canonical 行状态与来源表达，区分 `traded`、`suspended_confirmed`、`synthetic_gap_fill`、`source_unresolved`，禁止把无充分证据的补行伪装为正常停牌行。
- 为关键字段引入 `source` / `confidence` 治理规则，重点覆盖 `pre_close`、`adj_factor`、`turnover_rate` 及 `daily_basic` 派生字段。
- 将 `BJ` 纳入正式治理范围，并按 `2021-11-15` 前后拆分“历史映射治理”和“正式北交所数据源治理”。
- 建立 `v2` 的分层审计与升格门禁，分别定义 canonical gate 与 runtime gate。
- 新增 `v2` runtime compatibility 层，服务 `V10.1` 等现有 baseline，避免策略直接消费未经筛选的 canonical 补行。

## Capabilities

### New Capabilities
- `cn-stock-v2-source-governance`: 定义 A 股 `v2` 主表与侧表的主源、补源、审计源、交易所分层和字段可获得性规则。
- `cn-stock-v2-canonical-quality-governance`: 定义 `pams_ohlcv_daily_v2` 的行状态、来源标记、可信度标记、补值边界和 unresolved 表达。
- `cn-stock-v2-audit-and-gate-governance`: 定义 `v2` 的分市场、分阶段、分层门禁与审计汇总规则。
- `cn-stock-v2-runtime-compat-governance`: 定义 `v2` canonical 到 runtime 消费层的兼容规则，以及 `V10.1` 等 baseline 的数据消费约束。

### Modified Capabilities
- `api-runtime-config-compilation`: 增加对 `v2` canonical/runtime 数据角色与 compat 视图选择的运行时编译约束。

## Impact

- 数据库对象：`pams_ohlcv_daily_v2`、`pit_stock_moneyflow_v2`、`pams_ohlcv_daily_v2_audit_daily`、`pams_ohlcv_daily_v2_exceptions` 及相关 raw 表。
- 配置与运行时：`backend/configs/*`、runtime 数据源编译、baseline 数据消费路径。
- CLI 与运维：`backend/cli/managed/*` 回填、审计、门禁、质量报告脚本。
- 文档与治理：`docs/db/*` schema contract、runbook、source matrix、审计说明。
