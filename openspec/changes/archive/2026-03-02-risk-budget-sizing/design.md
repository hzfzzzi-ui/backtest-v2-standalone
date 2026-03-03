## Context

当前仓位管理由三个独立机制拼凑：
1. **等权分配**：`target_amount = nav / max_positions`（`portfolio_builder.py:273`）
2. **波动率调仓**（feature-flagged）：`vol_target = target_amount * vol_pct / (atr/price)`（`portfolio_builder.py:315-321`）
3. **二元熔断**：回撤 ≥15% → 全部禁买，≤10% → 恢复（`portfolio_simulator_strict.py:270-279`）

三者无统一风险预算概念，等权忽略个股波动差异，vol sizing 仅做 ATR 反比缩放但不涉及组合风险上限，breaker 是非此即彼的开关。

## Goals / Non-Goals

**Goals:**
- 实现"组合风险 → 回撤缩放 → 单笔风险 → ATR 定仓"的自上而下风险预算
- 渐进式回撤保护取代二元熔断（四档缩放 + 红线停止）
- 仓位公式与止损距离一致（共用 `atr_stop_k`）
- 完整可观测性（每日 risk budget 字段 + 各档触发 counter）
- 前端 workbench 可配置所有参数

**Non-Goals:**
- 趋势分级（benchmark MA20/MA60/MA120 结构判定）— 本次 `trend_multiplier` 固定 1.0，预留接口
- Regime filter 连续值微调 — 后续扩展
- 改变退出规则逻辑 — 仅统一 `atr_stop_k` 配置来源
- 改变信号生成逻辑

## Decisions

### D1: 新增 `RiskBudgetConfig` 替代 vol sizing + drawdown breaker

在 `models.py` 新增独立的 `RiskBudgetConfig` dataclass，同时：
- 从 `SizingConfig` 删除 `enable_volatility_sizing` 和 `vol_target_risk_pct`
- 从 `RiskConfig` 删除 `enable_drawdown_breaker`、`drawdown_breaker_pct`、`drawdown_breaker_recover_pct`
- 从 `ExitConfig` 删除 `atr_stop_k`（移入 `RiskBudgetConfig`，退出规则读同一个值）

```python
@dataclass(slots=True)
class RiskBudgetConfig:
    enabled: bool = False
    base_portfolio_risk: float = 0.06
    trend_multiplier: float = 1.0       # 预留，本次固定 1.0
    dd_scale_10: float = 0.8            # 回撤 >10%
    dd_scale_15: float = 0.6            # 回撤 >15%
    dd_fixed_20: float = 0.03           # 回撤 >20% 固定组合风险
    dd_stop_pct: float = 0.25           # 红线，停止交易
    min_active_ratio: float = 0.6       # 分母下限 = max_positions × ratio
    atr_stop_k: float = 2.0             # ATR 止损倍数（仓位计算 + 退出共用）
```

当 `enabled=False` 时，走原有等权逻辑（`nav / max_positions`），保持向后兼容。

理由：统一配置来源，避免旧 vol sizing 和新 risk budget 共存产生冲突。`atr_stop_k` 放在此处确保仓位公式与止损距离一致。

### D2: 风险预算计算位置 — 仿真循环（`portfolio_simulator_strict.py`）

在 `_run_unified_loop()` 中，NAV/drawdown 计算之后、信号生成之前，新增 risk budget 计算：

```
dd_ratio = 1.0 - nav / peak_nav  (已有)

if dd_ratio >= 0.25 → block all buys, portfolio_risk = 0
if dd_ratio >= 0.20 → portfolio_risk = dd_fixed_20 (0.03)
if dd_ratio >= 0.15 → portfolio_risk = base × trend × dd_scale_15
if dd_ratio >= 0.10 → portfolio_risk = base × trend × dd_scale_10
else               → portfolio_risk = base × trend × 1.0

denom = max(len(positions) + len(pending_buys), max_positions × min_active_ratio)
per_trade_risk = portfolio_risk / denom
risk_amount = nav × per_trade_risk
```

`risk_amount` 通过 `build_rebalance_orders()` 的新参数传入。

理由：drawdown 数据在仿真循环中已经存在（`peak_nav`, `nav`），在此处计算避免数据传递开销。替代原 breaker 逻辑所在位置，改动最小。

### D3: 订单构建替换 — `portfolio_builder.py`

`build_rebalance_orders()` 新增 `risk_amount: float = 0.0` 参数。当 `risk_amount > 0` 时：

```python
atr = sig_meta.get("atr_last")
if atr and atr > 0:
    stop_distance = atr_stop_k * atr
    shares = risk_amount / stop_distance
else:
    # ATR 不可用 → 降级为等权
    shares = target_amount / px

shares = floor(shares / lot_size) * lot_size

# 安全上限: single_stock_cap
max_shares = (nav * single_stock_cap) / px
shares = min(shares, max_shares)
```

当 `risk_amount == 0` 时（`enabled=False`），走原有 `target_amount * order_value_scale` 等权逻辑。

理由：保持 `build_rebalance_orders()` 的兼容性。通过 `risk_amount` 是否为正判断是否启用 risk budget 路径。

### D4: `atr_stop_k` 统一读取

退出规则中的 ATR stop 当前从 `ExitConfig.atr_stop_k`（默认 2.0）读取。改为：
- `RiskBudgetConfig.atr_stop_k` 为唯一来源
- `ExitConfig.atr_stop_k` 字段删除
- 退出规则评估时从传入的 risk budget config 中读取 `atr_stop_k`

影响点：`sma_signal_provider.py`、`generic_signal_provider.py`、`regime_router_signal_provider.py` 中读取 `exit_cfg.atr_stop_k` 的位置。

理由：仓位公式按 `k × ATR` 计算风险预算，如果退出用不同的 `k`，会导致实际亏损与预算不一致。

### D5: 前端 UI — 合并到"仓位风控"区块

在 workbench 左侧面板"仓位风控"区块中：
- 移除旧"波动率调仓" checkbox + risk_pct 输入
- 移除旧"回撤熔断" checkbox + 触发/恢复阈值
- 新增"风险预算"区域：
  - 总开关 checkbox（默认关闭）
  - 基础组合风险 % 输入（默认 6）
  - ATR 止损倍数输入（默认 2.0）
  - 回撤缩放阈值组（10%/15%/20%/25%）— 可考虑高级折叠
  - 最小活跃持仓比例（默认 0.6）

### D6: 可观测性输出

**每日 daily_row 新增字段：**
- `portfolio_risk`: 当日组合风险（如 0.06）
- `per_trade_risk`: 当日单笔风险（如 0.0075）
- `dd_scale`: 当日回撤缩放系数（1.0 / 0.8 / 0.6 / fixed / stop）
- `trend_mult`: 趋势倍数（本次固定 1.0）

**counters 新增：**
- `dd_scale_08_count`: 0.8x 缩放触发天数
- `dd_scale_06_count`: 0.6x 缩放触发天数
- `dd_fixed_03_count`: 固定 3% 触发天数
- `dd_stop_count`: 停止交易触发天数
- `dd_stop_block_count`: 被停止交易拦截的买入信号总数

**原 drawdown_breaker 相关 counter 删除。**

### D7: 向后兼容策略

`RiskBudgetConfig.enabled` 默认 `False`：
- 现有 JSON config 无 `risk_budget` 字段时，系统行为与改动前完全一致
- `SizingConfig` 保留 `mode`、`order_value`、`reserve_cash_ratio`、`lot_size` 等非 vol sizing 字段
- 旧的 `enable_volatility_sizing` / `enable_drawdown_breaker` 字段在 config loader 中静默忽略（不报错）

## Risks / Trade-offs

- **ATR 不可用降级**：部分标的上市不足 14 天导致 ATR=NaN，降级为等权分配。风险：降级仓位可能偏大。缓解：降级路径使用 `nav / max_positions` 保守值。
- **单一 `atr_stop_k` 限制灵活性**：某些策略可能希望仓位用 2×ATR 但止损用 1.5×ATR。当前设计为简化一致性牺牲了这种灵活性。后续可拆分为 `sizing_atr_k` 和 `exit_atr_k`。
- **趋势倍数固定 1.0**：本次不接入趋势分级，强趋势无法放大仓位。影响有限：等价于中性市场模式。后续接入 benchmark MA 结构后自然解锁。
- **前端旧配置迁移**：已保存的实验配置若含 `enable_volatility_sizing=true`，加载后会被忽略。需要用户手动切换到 risk budget。缓解：config loader 静默忽略旧字段。
