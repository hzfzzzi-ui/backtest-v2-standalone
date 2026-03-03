## Context

VECTOR 引擎的 SMA 路径（`run_vector_portfolio_backtest_strict`）是唯一面向前端的引擎路径。该路径的信号生成链为：

```
strategy 对象 → getattr(strategy, "fast"/"slow") → compute_feature_matrices()
→ _rolling_mean_matrix()（始终 SMA） → 信号矩阵 → 逐日执行
```

策略类的 `generate_signals()` 方法**从未被调用**——只有 CompositeStrategy 才走 Generic 路径。因此配置 `ema_cross` 与 `sma_cross` 的实际行为完全相同。

订单 sizing 方面，SMA 路径在 `portfolio_simulator_strict.py` L270 硬编码 `target_amount = NAV / max_positions`，忽略了配置中的 `base_order_value`。

## Goals / Non-Goals

**Goals:**
- 让 `ma_type` 参数在 VECTOR 引擎 SMA 路径中真正生效：EMA 用 `ewm()`，SMA 用 `rolling()`
- 支持 `base_order_value` 作为固定每仓目标金额，受可用现金约束
- 新增方案 A 的实验配置文件，确保所有参数可一键验证
- 在 audit.json / run_meta.json 中记录实际使用的 `ma_type`，使参数可观测

**Non-Goals:**
- 不修改 Generic 路径（CompositeStrategy）的逻辑
- 不修改前端 UI（配置参数已有前端支持）
- 不引入新的策略类型——复用现有 `ema_cross` / `sma_cross` registry 路由

## Decisions

### D1: 在 features.py 新增 `_ewm_mean_matrix()` 并参数化 `compute_feature_matrices()`

**选择**: `compute_feature_matrices()` 新增参数 `ma_type: str = "SMA"`。当 `ma_type == "EMA"` 时，`fast_ma` 和 `slow_ma` 使用 `_ewm_mean_matrix()`；trend/strength 相关 MA 始终保持 SMA（趋势过滤器不受策略 MA 类型影响）。

**替代方案**: 让 EMA_CROSS 走 Generic 路径。

**理由**: Generic 路径逐日调用 `generate_signals()`，性能远低于 SMA 路径的矩阵批量计算。在 800 只标的 × 1200+ 交易日的场景下，矩阵路径是必须的。新增一个 EWM 矩阵函数的改动极小（~15 行），与现有 `_rolling_mean_matrix()` 并列。

### D2: strategy 对象提供 `ma_type` 属性

**选择**: 在 `EMACrossStrategy` 中增加 `self.ma_type = "EMA"` 属性，`SMACrossStrategy` 中增加 `self.ma_type = "SMA"`。VECTOR 引擎通过 `getattr(strategy, "ma_type", "SMA")` 读取。

**理由**: 与现有 `fast` / `slow` 属性读取方式一致，无需修改 `StrategyConfig` 模型或 registry 签名。零破坏性。

### D3: 固定金额 sizing 模式

**选择**: VECTOR 引擎 SMA 路径在计算 `target_amount` 时，优先检查 strategy.state 中的 `base_order_value`。逻辑：

```python
cfg_order_value = float(strategy.state.get("base_order_value", 0))
if cfg_order_value > 0:
    target_amount = cfg_order_value
else:
    target_amount = float(nav) / float(max_positions)
```

配置链路：前端 `base_order_value` → overrides → `experiment_runner.py` L75 写入 `sizing.order_value` → `portfolio_builder.py` L644 已有 `strategy.state["base_order_value"] = ...`。需要修改 L644 的赋值逻辑，在有显式配置时使用配置值。

**替代方案**: 始终用 `NAV / max_positions`。

**理由**: 用户需要控制每仓目标金额以避免最低佣金问题。固定 30k/仓 × 3 仓 = 90k 部署 → gross_exposure ≈ 0.85，远优于当前 0.41。

### D4: 配置文件传递 `base_order_value` 到引擎

**选择**: 在 `experiment_runner.py` 中，从合并后的 cfg 读取 `sizing.order_value`，传递给 `run_portfolio_backtest()` → `run_vector_portfolio_backtest_strict()`。在 VECTOR 引擎中，使用此值覆盖 `strategy.state["base_order_value"]` 的默认计算。

**链路**:
```
config JSON: sizing.order_value = 30000
→ experiment_runner: merge_config() 已有 L75 逻辑
→ portfolio_builder.py L644: 优先使用 sizing.order_value
→ VECTOR 引擎内部 target_amount 使用此值
```

## Risks / Trade-offs

**[正确性] EWM 与 SMA 信号不同** → 这正是目标。EMA 对近期价格更敏感，信号时机会有差异。需通过实验验证。

**[sizing] base_order_value 超过可用现金** → 已有 `if net > cash: continue` 保护（引擎 L374）。当现金不足时自动跳过买入，自然降低实际持仓数。不会出现透支。

**[兼容] 现有 sma_cross 配置** → D2 中 `SMACrossStrategy` 的 `ma_type` 默认为 `"SMA"`，`compute_feature_matrices()` 的 `ma_type` 默认为 `"SMA"`。所有现有配置行为不变。

**[sizing 兼容] 不指定 base_order_value** → D3 的逻辑在 `cfg_order_value <= 0` 时回退到 `NAV / max_positions`，现有行为不变。
