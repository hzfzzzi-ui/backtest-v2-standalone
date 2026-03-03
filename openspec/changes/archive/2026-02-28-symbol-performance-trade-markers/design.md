## Context

当前工作台已有组合净值、回撤、基准 K 线与交易明细，但缺少“按个股复盘”的闭环能力。用户需要在同一页面完成：个股收益/回撤排序、个股筛选、买卖点与基准对照。  
现有数据基础满足快速实现路径：`portfolio_trades.csv`、`portfolio_daily.csv`、基准序列接口、通用 artifacts 读取接口。

约束：
- 不改变回测撮合主流程，不引入新执行语义；
- 先采用快速口径，保证性能与可解释性；
- 口径必须可追溯到产物字段，前端可验证。

## Goals / Non-Goals

**Goals:**
- 提供个股级收益/回撤榜单，默认收益降序。
- 提供个股筛选后曲线对照（个股 vs 基准）。
- 在曲线上叠加买卖箭头标记（绿买红卖）。
- 个股收益口径包含未平仓近似：以区间末日收盘价估值。
- 新增稳定产物 `symbol_performance` 并纳入 artifacts 协议。

**Non-Goals:**
- 不做精确逐日持仓重建（本次不构建完整逐日个股权益曲线引擎）。
- 不重构现有 benchmark 接口语义（新增 symbol 序列接口，避免混用）。
- 不新增策略参数，不影响既有回测结果口径。

## Decisions

### D1. 采用“快速口径 + 末日估值近似”
- 方案：基于成交配对得到已平仓净收益；对未平仓头寸按区间最后交易日收盘价估值并计入收益。
- 原因：实现成本低、可读性高，且满足“回测后快速筛选对比”目标。
- 备选：
  - 逐日重放个股权益曲线（精确但实现重、计算成本高）；
  - 仅统计已平仓（会低估持仓贡献，不满足需求）。

### D2. 新增独立个股序列 API
- 方案：新增 `/api/backtest_v2/series/symbol`，返回个股归一化序列（可含 OHLC）。
- 原因：`/series/benchmark` 当前语义是基准数据，复用会导致职责混乱。
- 备选：扩展 benchmark API 加 `type` 参数；但会增加兼容与调用歧义。

### D3. 新增 `symbol_performance` 产物并登记 artifacts
- 方案：在实验产物稳定化阶段输出 `symbol_performance.csv/json`，字段至少包括：`symbol, return_pct, max_drawdown, net_pnl, trades, unrealized_approx_pnl`。
- 原因：前端通过通用 artifacts/read 直接消费，避免页面端重复重算。
- 备选：前端实时从 trades 计算；但口径难统一、加载慢且不易复现。

### D4. 前端交互放在绩效图区域
- 方案：在现有 perf 区域新增“个股分析面板”，包含榜单、筛选、排序与图表模式切换。
- 原因：用户心智最接近“收益/回撤分析”，并可复用现有图表容器和基准切换。
- 备选：独立新标签页；但会割裂操作路径。

## Risks / Trade-offs

- [风险] 快速口径对长持仓未平仓收益存在近似误差  
  → Mitigation：在字段中显式输出 `unrealized_approx_pnl`，并在 UI 标注“近似估值”。

- [风险] 末日停牌或缺失收盘价导致未平仓估值异常  
  → Mitigation：采用“最近可用收盘价回溯”并输出 `valuation_fallback_used` 标志。

- [风险] 交易标记点数量大时图表性能下降  
  → Mitigation：默认仅展示当前选中个股的标记，限制初始 marker 数量并支持按区间缩放。

- [风险] 与现有 benchmark-candlestick 行为耦合  
  → Mitigation：保留原默认展示逻辑，仅在用户选择个股模式时切换数据源。

## Migration Plan

1. 后端先落地 `symbol_performance` 产物与 `/series/symbol` 接口，保证接口单测通过。  
2. 前端接入榜单与图表 marker，默认关闭个股模式，不影响现有组合视图。  
3. 开启灰度验证：对最近实验产物回填 `symbol_performance`，检查口径一致性。  
4. 若出现性能或口径争议，可回退到“仅榜单不叠加 marker”的中间形态。

## Open Questions

- 未平仓估值回溯天数上限是否需要配置（例如最多回溯 5/10 个交易日）？
- 个股曲线默认使用收盘价线图还是 K 线图（建议先线图，K 线作为增强）？
- 排序二级键是否固定为 `net_pnl`（收益率相同时）？
