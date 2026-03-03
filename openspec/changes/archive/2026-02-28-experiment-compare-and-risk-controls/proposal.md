## Why

当前工作台每次只能查看一个实验结果，无法快速对比不同参数/策略的效果差异，导致参数调优效率低下。同时，引擎的风控体系缺少止盈、固定百分比止损、波动率调仓和回撤熔断等关键机制，回测结果无法反映真实风控约束。

两个方向同时推进：有了对比功能后，风控增强的效果可以直接 A/B 验证。

## What Changes

### 多实验对比
- 在历史面板中支持勾选多个实验，弹出对比视图
- Level 1：KPI 对比表（收益、回撤、夏普、交易次数等），含 Δ 列
- Level 2：NAV 曲线叠加渲染（多条净值线同一图表，支持基准线）

### 风控增强
- 新增**止盈退出**：持仓浮盈达到阈值（固定百分比或 ATR 倍数）时平仓
- 新增**固定百分比止损**：不依赖 ATR 的简单百分比止损（如 -5% 即平仓）
- 新增**波动率调仓**：用 ATR 反向调整仓位大小（高波动 → 小仓位）
- 新增**回撤熔断**：组合回撤超过阈值时暂停开仓，回撤恢复后解除
- 所有新增规则必须有 reason_code 和计数器输出，可在 UI 验证

## Capabilities

### New Capabilities
- `experiment-compare`: 多实验 KPI 对比表 + NAV 曲线叠加功能
- `take-profit-exit`: 止盈退出规则（固定百分比 / ATR 倍数两种模式）
- `fixed-pct-stop-loss`: 不依赖 ATR 的固定百分比止损
- `volatility-sizing`: 基于 ATR 的波动率反比调仓
- `drawdown-circuit-breaker`: 组合级回撤熔断（暂停开仓 + 自动恢复）

### Modified Capabilities
- `single-run-pipeline`: result.artifacts 新增 experiment-compare 所需的对比 API 端点
- `exit-stats-display`: 新增止盈、固定止损、熔断相关的 reason_code 和计数器展示

## Impact

- **前端**：`backtest_v2.js`（历史面板交互）、`artifacts.js`（对比视图渲染）、`charts.js`（多曲线叠加）、`ui-controls.js`（风控参数面板）、`index.html`（新增 UI 元素）
- **后端引擎**：`portfolio_simulator_strict.py`（退出优先级链 + 仓位计算逻辑）、`portfolio_builder.py`（波动率调仓公式）
- **配置**：`models.py`（新增 TakeProfitConfig / DrawdownBreakerConfig 等配置模型）
- **API**：可能新增 `/api/backtest_v2/experiments/compare` 端点（批量读取多实验 perf + nav）
- **产物协议**：新增 reason_code（`TAKE_PROFIT`、`FIXED_STOP_LOSS`、`DRAWDOWN_BREAKER`）和对应计数器
