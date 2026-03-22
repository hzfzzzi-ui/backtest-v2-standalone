## Context

当前 `update_pams_ohlcv_daily` 已具备：

- 按交易日抓取 `daily`、`adj_factor`、`daily_basic`；
- 对同一 `(symbol, market, trade_date)` 做 upsert；
- 支持显式 `--start/--end` 重跑一个日期区间。

但它缺两件关键能力：

1. 没有“只修 `adj_factor` 缺口日期”的正式入口。显式重跑整段虽然可行，但范围过大，也无法从 summary 直接回答“修复后还剩多少缺口”。
2. `market_data_sync_service` 当前只看 `latest_cn_a_after >= target_trade_date` 是否成立，不能把数据完整性失败升级为同步失败。

## Goals / Non-Goals

**Goals**

- 提供最小改动的 `adj_factor` 缺口 repair 模式。
- 让 repair 模式和常规更新模式共享同一套抓取、归一化、upsert 逻辑。
- 在 summary 中显式暴露 `adj_factor` 修复前后缺口审计。
- 让日常同步服务对 `adj_factor` 缺口保持失败敏感，而不是仅对日期追平敏感。

**Non-Goals**

- 不引入 AKShare 作为本次修复的主抓取源。
- 不改动 `pg_provider` 当前的前向填充策略。
- 不修改回测运行时 `run_meta` 结构。
- 不扩展到 `circ_mv`、`float_share`、`free_share` 的历史修复。

## Decisions

### 决策 1：新增 `repair_null_adj_factor` 显式模式，而不是重写现有增量链路

原因：

- 当前 updater 的抓取与 upsert 主链已经可复用，问题不在数据写法，而在缺乏“按缺口日期定向重抓”的入口。
- 用布尔 repair 模式最小化改动面，避免新造第二套脚本。
- repair 模式只在给定日期范围内查询库中 `adj_factor IS NULL` 的交易日；若没有缺口日期，则直接 `noop`。

约束：

- repair 模式必须复用现有 `daily / adj_factor / daily_basic` 抓取和 `_normalize_cn_a_rows()` 逻辑。
- repair 模式不得改变默认增量模式的起止日期推断语义。

### 决策 2：完整性结果以“写库后数据库审计”为准，而不是只看抓取阶段缺口

原因：

- 抓取阶段的 `missing_adj_factor_rows` 只能说明本次归一化结果，不足以说明 upsert 后数据库里是否仍有缺口。
- 正式结果必须以写库后目标日期在数据库中的剩余 `adj_factor IS NULL` 统计为准。

实现要点：

- 新增数据库 helper，按交易日汇总 `market='CN_A' AND adj_factor IS NULL`。
- summary 记录 `before_dates`、`after_dates`、`remaining_rows`、`ok`。

### 决策 3：日常同步成功条件改为“追平目标日且 adj_factor 完整性通过”

原因：

- 只看日期追平会把“价格到了但复权因子缺失”的情况误判成成功。
- `adj_factor` 是 `hfq/qfq` 信号价格的关键基础字段，同步完成后仍缺失，应视为数据质量失败。

实现要点：

- `market_data_sync_service.run_cn_daily_sync_once()` 继续复用 `run_update_to_target()`。
- 如果 updater summary 标明本次覆盖日期的 `adj_factor` 完整性失败，则 `final_status` 必须为 `failed`。
- `summary_json` 中保留完整性审计字段，供 freshness/status 面板与后续排查读取。

## Risks / Trade-offs

- [风险] repair 模式如果日期范围过大，仍可能触发大量交易日抓取。
  - Mitigation: 只对“数据库中确有缺口的日期”发起抓取，不做整段盲刷。
- [风险] 个别 symbol 在 Tushare 当前仍可能无 `adj_factor` 返回，repair 后可能仍有残余缺口。
  - Mitigation: summary 必须显式记录剩余缺口日期和行数，同步服务将其标为失败而不是吞掉。
- [风险] 现有在途 `add-cn-daily-sync-and-freshness-status` change 也涉及 sync 服务。
  - Mitigation: 本次只修改 success/failure 判定与 updater summary，不扩 freshness UI 或状态面字段。

## Migration Plan

1. 为 `price-adjustment` 补充 delta spec，明确 repair 模式与严格失败判定。
2. 在 updater 中实现缺口日期扫描、repair 模式与写库后完整性审计。
3. 在 sync service 中接入完整性失败判定。
4. 补单测并执行针对性回归。

## Open Questions

- 本次不做 AKShare fallback；如果后续确认 Tushare 对个别 symbol 长期无 `adj_factor`，再单独立项扩展 fallback。
