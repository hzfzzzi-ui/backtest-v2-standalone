## ADDED Requirements

### Requirement: 特征矩阵向量化计算
引擎 SHALL 使用 DataFrame 级别的 `rolling()`/`ewm()` 操作代替 per-column Python 循环来计算特征矩阵（fast_ma、slow_ma、trend_fast_ma、trend_slow_ma、strength_ma、ATR）。

#### Scenario: Rolling Mean 全列并行
- **WHEN** 计算 `_rolling_mean_matrix(values, window)`
- **THEN** 使用 `pd.DataFrame(values).rolling(window).mean()` 一次性计算所有列，不使用 `for c in range(n)` 循环
- **AND** 结果矩阵数值与原实现一致（1e-10 精度内）

#### Scenario: EWM Mean 全列并行
- **WHEN** 计算 `_ewm_mean_matrix(values, span)`
- **THEN** 使用 `pd.DataFrame(values).ewm(span=span).mean()` 一次性计算所有列

#### Scenario: ATR 向量化
- **WHEN** 计算 ATR 矩阵
- **THEN** True Range 使用 numpy 广播计算（`np.maximum` 三路），rolling mean 使用 DataFrame 级别操作

---

### Requirement: OHLC 矩阵向量化填充
引擎 SHALL 使用 numpy fancy indexing 代替 `itertuples` 循环来填充 OHLC 矩阵。

#### Scenario: 矩阵填充
- **WHEN** 调用 `build_ohlc_matrices_from_history()`
- **THEN** 通过向量化 `map()` 生成行/列索引数组，使用 `matrix[row_arr, col_arr] = values_arr` 批量赋值
- **AND** 结果矩阵与原实现完全一致

---

### Requirement: 日循环热路径精简
引擎 SHALL 最小化日循环中的 Python 开销，包括：dict 分配、JSON 序列化、冗余索引查找。

#### Scenario: 行切片预提取
- **WHEN** SMA provider 的 `day_signals()` 需要访问信号矩阵
- **THEN** 每天预提取一次行切片（`sig_m["key"][i, :]`），候选循环中使用 `row_slice[c]` 代替 `sig_m["key"][i, c]`

#### Scenario: 调试数据条件化
- **WHEN** `debug_first_divergence=False`（生产模式）
- **THEN** `day_gate_by_symbol` 字典 SHALL NOT 被构建，跳过其全部 20+ 键的逐候选分配

#### Scenario: JSON 序列化延迟化
- **WHEN** 引擎构建 daily_rows
- **THEN** `json.dumps` 调用 SHALL 延迟到日循环结束后批量执行，或使用更快的序列化库

---

### Requirement: 回归等价性
所有性能优化 SHALL NOT 改变回测输出。

#### Scenario: 数值回归验证
- **WHEN** 优化后运行 SMA 回测（plan_a）和 Generic 回测（plan_a_ema_cross）
- **THEN** daily/trades/candidates CSV 与 Phase 4 基线 zero diff（数值精度 1e-10 内）
