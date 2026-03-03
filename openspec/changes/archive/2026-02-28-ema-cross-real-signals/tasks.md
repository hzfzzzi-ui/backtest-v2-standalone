## 1. EMA 信号计算

- [x] 1.1 在 `backend/core/engine_vector/features.py` 新增 `_ewm_mean_matrix(values, span)` 函数，使用 `pd.Series.ewm(span=span, min_periods=span).mean()` 计算 EWM 矩阵。DoD：函数存在，与 `_rolling_mean_matrix` 签名一致。
- [x] 1.2 修改 `compute_feature_matrices()` 新增参数 `ma_type: str = "SMA"`。当 `ma_type == "EMA"` 时，`fast_ma` 和 `slow_ma` 使用 `_ewm_mean_matrix()`；其余字段（trend_fast_ma、trend_slow_ma、strength_ma）始终用 SMA。DoD：`ma_type="EMA"` 生成的 fast_ma/slow_ma 与 `_ewm_mean_matrix` 输出一致。

## 2. 策略对象 ma_type 属性

- [x] 2.1 在 `backend/core/strategies/ema_cross.py` 的 `EMACrossStrategy.__init__()` 中设置 `self.ma_type = "EMA"`。DoD：`getattr(strategy, "ma_type")` 返回 `"EMA"`。
- [x] 2.2 在 `backend/core/strategies/sma_cross.py` 的 `SMACrossStrategy.__init__()` 中设置 `self.ma_type = "SMA"`。DoD：`getattr(strategy, "ma_type")` 返回 `"SMA"`。
- [x] 2.3 在 `portfolio_simulator_strict.py` SMA 路径中，读取 `ma_type = str(getattr(strategy, "ma_type", "SMA")).upper()`，传入 `compute_feature_matrices(ma_type=ma_type)`。DoD：EMA 策略产生 EMA 信号，SMA 策略产生 SMA 信号。

## 3. 固定金额 sizing

- [x] 3.1 在 `experiment_runner.py` 中，从合并后 cfg 读取 `sizing.order_value`，通过新参数 `base_order_value` 传递给 `run_portfolio_backtest()` → `run_vector_portfolio_backtest_strict()`。DoD：配置中的 `sizing.order_value=30000` 能到达引擎。
- [x] 3.2 修改 `portfolio_builder.py` L644 的 `strategy.state["base_order_value"]` 赋值逻辑：当显式传入 `base_order_value > 0` 时使用配置值，否则回退到 `NAV / max_positions`。DoD：`strategy.state["base_order_value"]` 反映配置值或默认计算值。
- [x] 3.3 修改 VECTOR 引擎 SMA 路径中订单 target_amount 的计算（当前 L270 区域的逻辑在引擎内部），使用 `strategy.state["base_order_value"]` 替代硬编码的 `NAV / max_positions`。DoD：target_amount 使用配置的 base_order_value。
- [x] 3.4 对 Generic 路径做同样的 target_amount 修改（保持两条路径一致）。DoD：Generic 路径也支持 base_order_value sizing。

## 4. 实验配置文件

- [x] 4.1 新建 `backend/configs/plan_a_ema_cross.json`，包含方案 A 全部参数：strategy.name="ema_cross", fast=8, slow=55, max_positions=6, sizing.order_value=30000, lot_size=100, initial_capital=100000, universe_mode=ALL_A, universe_limit=800, min_avg_turnover_20d=2e8。DoD：配置文件存在且 JSON 合法。

## 5. 可观测性

- [x] 5.1 在 VECTOR 引擎 SMA 路径的 metrics 输出中增加 `"ma_type"` 字段，记录实际使用的 MA 类型。DoD：`metrics["ma_type"]` 为 `"EMA"` 或 `"SMA"`。

## 6. 构建与验证

- [x] 6.1 Docker 重建并使用 `plan_a_ema_cross.json` 配置运行回测，验证：(1) audit.json 中 cash_check_fail = 0 ✓ (2) trades CSV 中佣金大部分为 `金额×0.0003` 而非 5.0 最低佣金 ✓ (100% above min) (3) run_meta 或 metrics 中 ma_type = "EMA" ✓ (4) gross_exposure 均值 > 0.55 ✗ (0.32，策略在2020-2024亏损74%导致现金不足，非实现问题)。DoD：1-3通过，4因策略盈利能力未达标。
