## 设计决策

### D1: features.py — DataFrame 级别并行替代 per-column 循环

**现状**：`_rolling_mean_matrix`、`_ewm_mean_matrix`、ATR 计算均使用 `for c in range(n)` 循环，每列构造 `pd.Series` + `rolling()/ewm()` + 散列回 numpy。5000 列 × 5 个特征 = 25000 次循环迭代。

**方案**：

```python
# _rolling_mean_matrix 重写
def _rolling_mean_matrix(values: np.ndarray, window: int) -> np.ndarray:
    return pd.DataFrame(values).rolling(window, min_periods=window).mean().to_numpy(dtype=float)

# _ewm_mean_matrix 重写
def _ewm_mean_matrix(values: np.ndarray, span: int) -> np.ndarray:
    return pd.DataFrame(values).ewm(span=span, min_periods=span).mean().to_numpy(dtype=float)
```

**NaN 处理差异**：原实现对每列独立提取 valid 行子集 → rolling → 散列回原位。DataFrame 级别 rolling 对 NaN 的处理方式不同（NaN 参与 window 计数）。需验证：
- 如果列中 NaN 是连续前缀（前 N 天无数据），两种方式等价（min_periods 保证前 N 天输出 NaN）
- 如果列中有中间 NaN（停牌日），原实现跳过 NaN 继续 rolling，而 DataFrame 级别 rolling 会中断 window。**需要确认数据特征：A 股 OHLCV 数据中间 NaN 是否存在**。如果存在，需保留 per-column 逻辑或在 DataFrame rolling 后修补。

**决策**：先实现 DataFrame 级别替换，用回归测试验证。如果中间 NaN 导致 diff，回退到 per-column 但优化内部（消除 pd.Series 构造，直接用 np.ndarray + pd.DataFrame 单列）。

**ATR 向量化**：
```python
prev_close = np.roll(close, 1, axis=0)
prev_close[0, :] = np.nan
tr = np.maximum(high - low, np.maximum(np.abs(high - prev_close), np.abs(low - prev_close)))
atr = pd.DataFrame(tr).rolling(atr_n, min_periods=atr_n).mean().to_numpy(dtype=float)
```
同样的 NaN 处理风险。但 ATR 一般只在有完整 OHLC 的行上计算，且停牌日 OHLC 为 NaN → tr 为 NaN → rolling 自然跳过。

**RSI**：`_rsi_matrix` 的 Wilder smoothing 使用 `ewm(alpha=1/p, adjust=False)`。向量化需要对 `diff().clip()` 做 DataFrame 级别操作。由于 RSI 涉及 `reset_index` 跳过 NaN 行，与 NaN 处理紧密耦合，优先级较低——留到验证 rolling/ewm 安全后再处理。

---

### D2: data_matrix.py — numpy fancy indexing 替代 itertuples

**现状**：`build_ohlc_matrices_from_history` 使用 `hist.itertuples()` 逐行填充 6 个矩阵。每行 1 次 `pd.Timestamp().normalize()` + 2 次 dict lookup。

**方案**：
```python
# 1. 向量化构建行/列索引
hist["_row"] = hist["date"].dt.normalize().map(date_to_row)
hist["_col"] = hist["symbol"].map(sym_to_col)
valid = hist["_row"].notna() & hist["_col"].notna()
r_arr = hist.loc[valid, "_row"].to_numpy(dtype=int)
c_arr = hist.loc[valid, "_col"].to_numpy(dtype=int)

# 2. 批量赋值
open_m[r_arr, c_arr] = hist.loc[valid, "open"].to_numpy(dtype=float)
high_m[r_arr, c_arr] = hist.loc[valid, "high"].to_numpy(dtype=float)
low_m[r_arr, c_arr] = hist.loc[valid, "close"].to_numpy(dtype=float)  # 注意原代码 close
close_m[r_arr, c_arr] = hist.loc[valid, "close"].to_numpy(dtype=float)
volume_m[r_arr, c_arr] = pd.to_numeric(hist.loc[valid, "volume"], errors="coerce").to_numpy(dtype=float)

# 3. tradable 向量化
ok_price = (close_m[r_arr, c_arr] > 0) & (open_m[r_arr, c_arr] > 0)
                & ~np.isnan(close_m[r_arr, c_arr]) & ~np.isnan(open_m[r_arr, c_arr])
ok_volume = ~np.isnan(volume_m[r_arr, c_arr]) & (volume_m[r_arr, c_arr] > 0)
tradable[r_arr, c_arr] = ok_price & ok_volume  # 基础条件

# 4. suspended + ST 过滤后续标记
```

**ST 过滤**：`_is_in_st` 使用 per-row Python 调用，但 ST 数据量很小（百行级），可保留原逻辑但放在矩阵填充之后：
```python
# 先全量设置 tradable（不含 ST），然后逐 ST 区间清除
for col_idx, periods in st_lookup.items():
    for s_date, e_date in periods:
        row_mask = (dates >= s_date) & (dates <= e_date)
        tradable[row_mask, col_idx] = False
```

**suspended 列**：如果存在 `is_suspended` 列，同样向量化：
```python
if has_suspended:
    susp_vals = hist.loc[valid, "is_suspended"]
    is_susp = susp_vals.notna() & susp_vals.astype(bool)
    tradable[r_arr[is_susp], c_arr[is_susp]] = False
```

---

### D3: _build_price_indices — 批量列提取

**现状**：`itertuples` 逐行构建 `(date, symbol) -> price` 字典。

**方案**：
```python
dates_col = df["date"].dt.date.to_list()
syms_col = df["symbol"].to_list()
opens = df["open"].to_numpy(dtype=float)
closes = df["close"].to_numpy(dtype=float)
open_idx = dict(zip(zip(dates_col, syms_col), opens))
close_idx = dict(zip(zip(dates_col, syms_col), closes))
```
消除 per-row `pd.Timestamp(r.date).date()` 和 `str(r.symbol).lower()`（symbol 已在上游 lower 化）。

---

### D4: SMA day_signals — 行切片预提取 + debug guard

**行切片预提取**：在 `day_signals()` 顶部一次性提取当日行切片：
```python
_row_cross_up = sig_m["cross_up"][i, :]
_row_buffer_ok = sig_m["buffer_ok"][i, :]
_row_trend_ok = sig_m["trend_ok"][i, :]
_row_base_trend_on = sig_m["base_trend_on"][i, :]
# ... 共约 10 个矩阵
```
候选循环中使用 `_row_cross_up[c]` 代替 `sig_m["cross_up"][i, c]`，消除每候选 8+ 次 dict lookup + 2D 索引。

**debug guard**：`day_gate_by_symbol` 仅在 debug 模式使用。增加 `_collect_debug` 标志（precompute 时从 kwargs 获取），guard 整个 20-key dict 构建：
```python
if self._collect_debug:
    day_gate_by_symbol[sym] = { ... }
```

**multifactor 预计算**：`_build_daily_multifactor_scores` 中 `close[:, col] * volume[:, col]` 每候选重新计算。在 `precompute()` 中预计算 `self._amt_matrix = mx.close * mx.volume`，`day_signals` 中直接索引 `self._amt_matrix[i-19:i+1, c]`。

---

### D5: 统一循环 — JSON 延迟化 + 冗余消除

**JSON 延迟化**：`daily_rows` 中的 `top5_positions_json`、`top5_selected_strength_json`、`top5_rejected_strength_json` 改为存储原始 Python 对象（list/dict），循环结束后批量 `json.dumps`：
```python
# 循环中：
dr["_top5_positions"] = top5         # 存原始 list
dr["_top5_selected"] = sel_list[:5]  # 存原始 list
dr["_top5_rejected"] = rej_list[:5]  # 存原始 list

# 循环后：
for dr in daily_rows:
    dr["top5_positions_json"] = json.dumps(dr.pop("_top5_positions", []), ensure_ascii=False)
    dr["top5_selected_strength_json"] = json.dumps(
        [{"symbol": r.get("symbol"), "strength": r.get("strength")} for r in dr.pop("_top5_selected", [])],
        ensure_ascii=False,
    )
    dr["top5_rejected_strength_json"] = json.dumps(
        [{"symbol": r.get("symbol"), "strength": r.get("strength"), "reason": r.get("reject_reason")} for r in dr.pop("_top5_rejected", [])],
        ensure_ascii=False,
    )
```
注意：JSON 延迟化只移动了 json.dumps 调用位置，不改变最终输出。

**next_open 构建简化**：
```python
# 现状（3 次 list 分配 + set 转换）
next_open = {s: ... for s in set([...for x in sell_sigs + buy_sigs] + list(positions.keys()))}

# 优化
_syms = set(positions)
_syms.update(s.symbol for s in sell_sigs)
_syms.update(s.symbol for s in buy_sigs)
next_open = {s: float(open_idx.get((next_day, s), 0.0) or 0.0) for s in _syms}
```

**daily_rows 赋值合并**：将 25+ 次 `daily_rows[-1]["key"] = value` 合并为 `dr.update({...})` 单次调用。

---

### D6: _process_pending_fills — meta 缓存 + json.dumps 延迟

`od.get("meta")` 被重复调用 3 次/fill。缓存为 `_meta = od.get("meta") or {}`。`json.dumps(_meta)` 延迟到循环结束后批量处理。

---

## 优先级排序

| 优先级 | 改动 | 文件 | 预期加速 | 风险 |
|--------|------|------|----------|------|
| P1 | 特征矩阵 DataFrame 并行 | features.py | 预计算 10-50x | NaN 处理差异需验证 |
| P2 | OHLC 矩阵 fancy indexing | data_matrix.py | 预计算 10-30x | ST/suspended 逻辑需保留 |
| P3 | 价格索引批量构建 | portfolio_simulator_strict.py | 3-10x | 低 |
| P4 | 行切片预提取 + debug guard | sma_signal_provider.py | 日循环 2-3x | 低 |
| P5 | JSON 延迟化 + 冗余消除 | portfolio_simulator_strict.py | 日循环 minor | 低 |
| P6 | multifactor amt 预计算 | sma_signal_provider.py | MF 评分 2-5x | 低 |

## 回归验证策略

每个优先级完成后立即 Docker 重建 + 双路径（SMA plan_a + Generic plan_a_ema_cross）回归验证，对比 Phase 4 基线（exp_20260301_010551 / exp_20260301_010846）。如出现 NaN 差异，立即回退该改动。
