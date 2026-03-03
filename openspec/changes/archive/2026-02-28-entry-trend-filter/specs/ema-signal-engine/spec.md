## MODIFIED Requirements

### Requirement: 信号矩阵扩展入场过滤输出
`build_signal_matrices()` SHALL 新增两个布尔矩阵输出，供引擎在买入候选过滤阶段使用。

#### Scenario: 新增矩阵
- **WHEN** 调用 `build_signal_matrices()` 且传入 `enable_entry_above_slow_ma` 或 `enable_entry_slow_ma_slope` 参数
- **THEN** 返回字典 SHALL 新增：
  - `entry_above_slow_ma`: shape (t, n) bool 矩阵，`close[i,c] > slow_ma[i,c]`
  - `entry_slow_ma_slope_pos`: shape (t, n) bool 矩阵，`slow_ma[i,c] - slow_ma[i-lb,c] > 0`

#### Scenario: 引擎买入过滤集成
- **WHEN** 引擎 SMA 路径执行买入候选过滤
- **THEN** `raw_buy_mask` SHALL 在 tradable 过滤之后、排名之前，额外应用 `entry_above_slow_ma` 和 `entry_slow_ma_slope_pos` 的 AND mask（仅在对应 enable 参数为 true 时）
