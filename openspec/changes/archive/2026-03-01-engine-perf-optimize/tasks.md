## 1. features.py — 特征矩阵向量化 (D1)

- [x] 1.1 重写 `_rolling_mean_matrix`：替换 per-column 循环为 `pd.DataFrame(values).rolling(window, min_periods=window).mean().to_numpy()`。验证：回归 zero diff。
- [x] 1.2 重写 `_ewm_mean_matrix`：替换 per-column 循环为 `pd.DataFrame(values).ewm(span=span, min_periods=span).mean().to_numpy()`。验证：回归 zero diff。
- [x] 1.3 向量化 ATR 计算：True Range 使用 `np.roll` + `np.maximum` 广播，rolling mean 使用 DataFrame 级别操作。删除 `for c in range(n)` 循环。验证：回归 zero diff。
- [x] 1.4 Docker 重建 + 双路径回归验证（plan_a + plan_a_ema_cross），对比 Phase 4 基线。如 NaN 差异，回退并采用设计文档中的后备方案。

## 2. data_matrix.py — OHLC 矩阵向量化填充 (D2)

- [x] 2.1 重写 `build_ohlc_matrices_from_history`：使用 `hist["date"].dt.normalize().map(date_to_row)` + `hist["symbol"].map(sym_to_col)` 构建行/列索引数组，`matrix[r_arr, c_arr] = values_arr` 批量赋值。保留 suspended + ST 过滤逻辑（向量化或后置清除）。验证：回归 zero diff。

## 3. portfolio_simulator_strict.py — 价格索引 + 日循环精简 (D3, D5, D6)

- [x] 3.1 重写 `_build_price_indices`：使用 `df["date"].dt.date.to_list()` + `zip` 批量构建 dict，消除 per-row `pd.Timestamp().date()`。验证：回归 zero diff。
- [x] 3.2 日循环 JSON 延迟化：`top5_positions_json`、`top5_selected_strength_json`、`top5_rejected_strength_json` 改为循环中存原始对象，循环后批量 `json.dumps`。验证：回归 zero diff。
- [x] 3.3 日循环冗余消除：`next_open` 构建简化（set 直接构建）、`daily_rows[-1]` 赋值合并为 `dr.update()`、`_process_pending_fills` 中 `od.get("meta")` 缓存。验证：回归 zero diff。

## 4. sma_signal_provider.py — 行切片 + debug guard + multifactor (D4, D6)

- [x] 4.1 行切片预提取：在 `day_signals()` 顶部一次性提取 `sig_m["key"][i, :]` 行切片（约 10 个矩阵），候选循环中使用 `row[c]` 代替 `sig_m["key"][i, c]`。验证：回归 zero diff。
- [x] 4.2 debug guard：增加 `_collect_debug` 标志（precompute 时设置），`day_gate_by_symbol` 字典构建仅在 `_collect_debug=True` 时执行。验证：debug_first_divergence=True 路径功能不变。
- [x] 4.3 multifactor amt 预计算：在 `precompute()` 中预计算 `self._amt_matrix = mx.close * mx.volume`，`_build_daily_multifactor_scores` 中直接索引。验证：回归 zero diff。

## 5. 最终回归验证

- [x] 5.1 Docker 重建，运行 SMA 回测（plan_a），对比 Phase 4 基线 exp_20260301_010551 的 daily/trades CSV。验证：zero diff。（exp_20260301_014535）
- [x] 5.2 运行 Generic 回测（plan_a_ema_cross），对比 Phase 4 基线 exp_20260301_010846 的 daily/trades CSV。验证：zero diff。（exp_20260301_014549）
