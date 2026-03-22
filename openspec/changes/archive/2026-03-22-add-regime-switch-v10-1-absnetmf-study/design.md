## Context

当前仓库已经有两条可复用的结果源：

- `baseline_V10.1 / 2012-01-04 ~ 2026-03-16`
  - 正式实验目录：`outputs/experiments/exp_20260320_035043267_e2c1`
  - 产物中包含完整的 `portfolio_daily.csv`，并且日频上有 `trade_mode` 字段，可直接代表市场过滤器对组合的实际交易模式。
- `ABSNETMF_MA20 / corrected strict dynamic PIT / 2012-01-04 ~ 2026-03-16`
  - 研究目录：`outputs/ops/strict_pit_dynamic_absnetmf_vs_monthly_trend_12m_1226_v2_canonical_tradable_cov_20260319`
  - 产物中包含 `abs_portfolio_daily.csv` 与 `abs_nav.csv`，可重建日收益。

用户本次要验证的是一个**研究问题**，不是正式策略改造：

- 当 `V10.1` 市场过滤器处于牛市阶段时，继续用 `V10.1`
- 当处于非牛市阶段时，不再空仓或轻仓，而是用 `ABSNETMF`，但只给半仓，另一半保留现金

这件事如果直接改引擎，会把 L3 主线逻辑和 research 拼接混在一起；当前更合理的方式是基于已有两条独立结果做**收益壳拼接实验**。

## Goals / Non-Goals

**Goals:**

- 基于已有正式/研究产物构建一条 research-only 的混合净值线。
- 使用 `V10.1` 日频 `trade_mode` 作为唯一切换依据，避免重新定义市场过滤器。
- 输出可审计结果，明确每天使用的是哪条收益源、切换次数、各阶段贡献与总体绩效。

**Non-Goals:**

- 不把混合逻辑接入正式回测引擎。
- 不重算 `V10.1` 或 `ABSNETMF` 的信号、持仓、成交。
- 不在本次 change 中解决双策略真实换仓冲突、成交冲突和交易成本精确建模。
- 不把这条混合线包装成正式可交易策略。

## Decisions

### D1: 采用 research-only 的“日收益拼接壳”，不改正式引擎

本次实验只在研究层拼接两条已有净值序列：

- 当 `trade_mode == TREND_MAIN` 时，使用 `baseline_V10.1` 当日 `daily_return`
- 否则使用 `0.5 * ABSNETMF_daily_return`

原因：

- 这是最小改动方案，不污染正式主线。
- 两条底层策略都已经独立跑完，拼接实验只回答“阶段切换后总体效果如何”，不回答“真实交易级实现能否无摩擦落地”。

备选方案：

- 直接改 `engine_vector` 或组合执行器，把双策略共仓实现进引擎。放弃原因：这是正式 L3 主逻辑改造，不适合作为本轮最小实验。

### D2: 非牛市阶段定义为 `trade_mode != TREND_MAIN`

切换条件不直接使用 `market_state` 文本，而使用 `baseline_V10.1` 日产物里的 `trade_mode`：

- `TREND_MAIN`：视为牛市阶段，使用 `V10.1`
- 其他值（如 `TREND_LIGHT`、`NO_TRADE`）：视为非牛市阶段，使用 `0.5 * ABSNETMF + 0.5 cash`

原因：

- `trade_mode` 是 `V10.1` 市场过滤器实际落到组合层的最终行为口径，比单纯状态标签更贴近“策略真正在做什么”。

备选方案：

- 使用 `market_state == BULL`。放弃原因：它和组合层实际仓位控制不是完全同义，容易在研究解释上产生歧义。

### D3: 现金半仓按零收益处理

非牛市阶段的半仓现金部分收益固定为 `0`，所以混合日收益定义为：

- `hybrid_daily_return = abs_daily_return * 0.5`

原因：

- 这是用户明确指定的“半仓现金”口径。
- 当前项目没有统一的现金收益侧表，本次实验不应额外引入货基或利率假设。

### D4: 统一起始资金为 1,000,000，并按日收益重建混合净值

混合净值不直接拼接两边的绝对 NAV，而是：

- 从 `1,000,000` 起步
- 按每日选中的收益源 `daily_return` 递推

原因：

- `V10.1` 和 `ABSNETMF` 原始运行的起始资金不同，直接混合绝对 NAV 会污染结果。
- 用收益递推可以消掉起始资金差异。

## Risks / Trade-offs

- [Risk] 这不是订单级真实组合实现，而是收益拼接壳  
  → Mitigation：在报告和 summary 中显式标注 `research_only`，禁止表述成正式可交易策略。

- [Risk] 两条底层策略的数据角色不同（`V10.1` 当前是 `v1`，`ABSNETMF` 当前是 `v2_canonical`）  
  → Mitigation：在产物中明确写出底层数据口径，不把结果解读成“同数据底座公平对决”。

- [Risk] 切换日没有显式计入双边真实换仓摩擦  
  → Mitigation：输出切换次数与切换日期摘要，明确这是研究上界，不是实盘成交回放。

## Migration Plan

1. 新增本 change 的最小 proposal/design/spec/tasks。
2. 编写独立研究脚本，读取两条既有结果源并重建混合净值。
3. 输出 `summary.json`、`perf.json`、`hybrid_nav.csv`、`switch_log.csv`、`report.md`。
4. 如果结果值得继续，再另开 change 讨论是否做正式引擎级实现。

回退策略：

- 本次只新增研究脚本和 `outputs/ops` 产物。
- 需要回退时，删除该脚本与对应产物即可，不影响主线。

## Open Questions

- 是否要在下一轮把 `ABSNETMF` 也切到 `v1` 或把 `V10.1` 切到 `v2` 再做同底座实验；本次不处理。
- 是否要把非牛市阶段再细分成 `TREND_LIGHT` 与 `NO_TRADE` 两种不同 ABS 权重；本次先统一半仓。
