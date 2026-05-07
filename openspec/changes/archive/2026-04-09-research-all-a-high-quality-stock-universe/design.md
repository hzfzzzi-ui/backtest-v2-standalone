## Context

当前仓库中：

- `HS300_ZZ500` 依赖 `pit_index_constituents`
- `ALL_A` 不支持 `PIT_DYNAMIC`
- `ALL_A` 运行时从 `pit_security_master + OHLCV availability` 解析 as-of 活跃股票池

因此本研究不能定义成“全市场 PIT 指数成分”，而必须定义成：

- `ALL_A + as-of active universe`
- 再叠加高质量过滤

## Goals / Non-Goals

**Goals**
- 只改股票池，测试个股腿在 `2023-2026` 的窗口表现是否改善
- 检查交易标的是否显著降低对 `CSI800` 的重叠
- 给后续是否值得继续做 `ALL_A` 研究提供证据

**Non-Goals**
- 不修改 breakout / ranking / exit
- 不修改 ETF 腿
- 不修改账户层预算和状态机
- 不直接升级主线

## Decisions

### 1. 先做 stock-only A/B
- 原因：这样最可归因，避免 ETF 和账户预算掺入结果

### 2. 实验组使用 `ALL_A + 高质量过滤`
- 采用：
  - `universe_mode = ALL_A`
  - `universe.membership_mode = ""`
  - 保留现有过滤
  - `min_avg_turnover_20d = 2e8`
- 原因：先从数据库中数据质量和流动性更高的标的开始，降低微小盘噪音

### 3. 先看窗口收益与风格重叠
- 重点看：
  - `CAGR / Sharpe / MaxDD`
  - 实际交易标的与 `CSI800 / CSI1000` 的重叠
- 暂不把 ETF 相关性混进这轮研究

## Risks / Trade-offs

- `ALL_A` 不是 `PIT_DYNAMIC`，因此研究口径与当前主线不同
- 全市场即使加流动性门槛，仍可能引入更多风格漂移
- 如果结果改善，也不能直接说明可以升格主线，只能说明值得继续细化
