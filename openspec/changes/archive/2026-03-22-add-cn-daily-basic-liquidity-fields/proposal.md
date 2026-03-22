## Why

当前系统已经把 `volume` 与 `turnover` 纳入日线主库和回测主链路，但缺少 A 股日频换手率口径，导致股票池流动性过滤和后续放量研究只能使用绝对成交额。对 A 股横截面研究而言，成交额不能替代换手率，继续沿用同一字段语义会放大价格、市值与板块差异带来的失真。

现在补齐这条数据链路，可以在不破坏 baseline 的前提下，把“成交额过滤”和“换手率过滤”明确拆开，并为后续基于 `turnover_rate_f` 的研究提供可审计、可复现的输入口径。

## What Changes

- 为 `pams_ohlcv_daily` 中 `market='CN_A'` 的日线记录追加 nullable 的 daily_basic 流动性字段：`turnover_rate`、`turnover_rate_f`、`volume_ratio`。
- 可选追加 supporting fields：`float_share`、`free_share`、`circ_mv`，用于审计与后续扩展，但不改变当前 baseline 必需字段集合。
- 新增官方 `daily_basic` 日频流动性字段的导入/回填链路，按 `symbol + trade_date` 写入，并保持现有 `turnover=成交额` 语义不变。
- 扩展运行时数据提供层，对新增流动性字段进行可选透传；默认配置下现有 OHLCV 消费路径与 baseline 行为保持不变。
- 新增独立的换手率过滤配置，默认关闭；现有 amount-based 流动性过滤继续保留。
- 在数据校验/审计中加入“成交额 vs 换手率”语义检查、字段可用性检查与时间对齐约束，避免静默混用。

## Capabilities

### New Capabilities
- `cn-daily-basic-liquidity-data`: 为 CN A 日线数据提供可审计的 daily_basic 流动性字段入库、运行时透传与可选换手率过滤契约

### Modified Capabilities

## Impact

- 数据库：`pams_ohlcv_daily` 表结构与历史回填流程
- 数据接入：官方 `daily_basic` 导入/更新脚本
- 运行时数据层：`backend/core/data/*`
- 股票池过滤与数据 bundle：`backend/core/universe/*`、`backend/core/tools/*`
- 数据校验与研究审计：`backend/core/data/validate_pg.py`、`backend/core/audit/*`
- 测试：provider、data bundle、universe filter、validate_data、research audit 相关单元/集成测试

## Usage Notes

- `turnover` 继续表示成交额，运行时 canonical `amount <- turnover` 的旧口径保持不变。
- `turnover_rate` / `turnover_rate_f` 只表示换手率，不允许覆盖或重命名现有 `turnover`。
- 新增字段按 optional extras 透传；未启用换手率过滤时，baseline 配置与结果不变。

最小启用示例：

```json
{
  "universe": {
    "filters": {
      "exclude_st": true,
      "exclude_suspended": true,
      "min_list_days": 120,
      "min_avg_turnover_20d": 100000000,
      "min_avg_turnover_rate_20d": 1.0,
      "turnover_rate_field": "turnover_rate_f",
      "price_min": 5.0,
      "limit_rule": "ignore"
    }
  }
}
```

## Minimal Experiment Template

- baseline: 仅使用现有 `min_avg_turnover_20d` 成交额过滤，`min_avg_turnover_rate_20d=0`
- variant: 保持其他 universe/filter/exec 口径不变，只新增 `min_avg_turnover_rate_20d > 0`，建议首轮只测试 `turnover_rate_field='turnover_rate_f'`
- 审计约束：daily_basic 仅按 `t` 日收盘后观测、`t+1` 执行；缺失值不做 `bfill`，字段缺失时直接 fail-fast
- 对比指标：股票池规模、行业分布、交易次数、CAGR、MaxDD、Sharpe、Calmar，不把数据补齐和策略优化绑定在同一轮
