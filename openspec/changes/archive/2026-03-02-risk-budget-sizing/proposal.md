## Why

当前仓位管理采用"等权分配 + 可选波动率调整 + 二元熔断"的拼凑结构：等权分配（`nav / max_positions`）忽略个股波动差异，波动率调仓（feature-flagged）仅做 ATR 反比缩放但无风险预算概念，回撤熔断是开/关二值状态无法渐进降险。三者缺乏统一的风险预算框架，无法实现"从组合风险到单笔仓位"的自上而下分配。

需要一套系统化风险预算仓位管理：组合风险上限 → 回撤缩放 → 单笔风险分配 → ATR 止损定仓，替代现有三个独立机制。

## What Changes

- **新增 `RiskBudgetConfig`**：统一的风险预算配置（基础组合风险 6%、趋势倍数预留 1.0、回撤缩放阈值、红线 25%、分母下限比例、ATR 止损倍数 k=2.0）
- **新增风险预算计算引擎**：每日在仿真循环中计算 `portfolio_risk → per_trade_risk → risk_amount`，传递给订单构建
- **新增 ATR 定仓公式**：`shares = risk_amount / (k × ATR)`，替代等权分配和旧 vol sizing
- **新增渐进回撤缩放**：dd>10% → 0.8x, dd>15% → 0.6x, dd>20% → 固定 3%, dd≥25% → 停止交易，替代二元熔断
- **废弃 `enable_volatility_sizing` / `vol_target_risk_pct`**：旧波动率调仓逻辑完全移除
- **废弃 `enable_drawdown_breaker` / `drawdown_breaker_pct` / `drawdown_breaker_recover_pct`**：旧二元熔断完全移除
- **统一 `atr_stop_k`**：仓位计算和退出规则 ATR 止损共用同一个 k 值（默认 2.0）
- **前端 UI 更新**：workbench "仓位风控"区块新增 risk budget 参数控件，移除旧波动率调仓和旧熔断控件
- **可观测性**：每日 row 新增 `portfolio_risk`、`per_trade_risk`、`dd_scale`、`trend_mult` 字段；counter 新增各档回撤缩放触发次数

## Capabilities

### New Capabilities
- `risk-budget-sizing`: 系统化风险预算仓位管理 — 从组合风险到单笔仓位的自上而下分配框架

### Modified Capabilities
- `volatility-sizing`: **REMOVED** — 旧 ATR 反比调仓被 risk-budget-sizing 完全替代
- `drawdown-circuit-breaker`: **REMOVED** — 旧二元熔断被渐进回撤缩放完全替代

## Impact

- **后端 config**：`backend/core/config/models.py` — 新增 `RiskBudgetConfig`，删除 `SizingConfig.enable_volatility_sizing` / `vol_target_risk_pct`，删除 `RiskConfig.enable_drawdown_breaker` / `drawdown_breaker_pct` / `drawdown_breaker_recover_pct`
- **后端引擎**：`backend/core/engine_vector/portfolio_simulator_strict.py` — 替换 drawdown breaker 为渐进缩放，计算 risk_budget 并传给 portfolio_builder
- **后端订单**：`backend/core/portfolio/portfolio_builder.py` — 替换等权 + vol sizing 为 ATR 定仓公式
- **后端配置加载**：`backend/core/config/loader.py` — 加载 RiskBudgetConfig
- **后端 API**：`backend/api/endpoints/backtest_v2.py` — 透传 risk budget 参数
- **后端实验**：`backend/core/tools/experiment_runner.py` — 透传 risk budget 配置
- **前端**：`frontend/assets/js/backtest_v2.js` — "仓位风控"区块新增 risk budget UI 控件
- **前端**：`frontend/index.html` — 新增 risk budget 表单元素
- **产物协议**：daily row 新增 4 个字段，counters 新增回撤缩放统计
