## Why

Phase 4 完成了 SignalProvider 协议统一后，`portfolio_simulator_strict.py` 从 1812 行降至 973 行，代码结构清晰。但性能瓶颈依然存在：`features.py` 中的 per-column Python 循环（5000 列 × 5 个特征矩阵 = 25000 次 pandas Series 构造）、`data_matrix.py` 的 `itertuples` 逐行填充（5000 符号 × 2500 天 = 1250 万次循环）、以及日循环中的 `json.dumps`/dict 分配/冗余索引查找等开销。全 A 股回测（800+ 符号 × 5 年）预计算耗时可达 10+ 秒，日循环中每天约 40 次 dict 赋值 + 3 次 json.dumps。Phase 5 目标：通过向量化预计算和精简日循环热路径，将端到端回测耗时减少 30–50%。

## What Changes

- **向量化特征计算**：将 `features.py` 中 `_rolling_mean_matrix`、`_ewm_mean_matrix`、ATR 计算从 per-column 循环改为 `pd.DataFrame.rolling()/ewm()` 全列并行操作
- **向量化矩阵填充**：将 `data_matrix.py` 中 `build_ohlc_matrices_from_history` 的 `itertuples` 循环替换为 numpy fancy indexing
- **向量化价格索引构建**：将 `_build_price_indices` 的 `itertuples` 循环替换为批量列提取
- **日循环热路径精简**：
  - 行切片预提取：SMA provider 中 `sig_m["key"][i, c]` 的重复 dict+2D 索引改为每天预提取行切片
  - 调试数据条件化：`day_gate_by_symbol` 大字典构建仅在 `debug_first_divergence=True` 时执行
  - 多因子评分预计算：`_build_daily_multifactor_scores` 中 `close * volume` 矩阵一次性预计算
  - JSON 序列化延迟化：`json.dumps` 从每日执行改为循环结束后批量执行
  - 冗余操作消除：`next_open` dict 构建中的重复 list→set 转换、`daily_rows[-1]` 的逐字段赋值合并

## Capabilities

### New Capabilities
- `engine-perf-optimize`: 覆盖预计算向量化（features/data_matrix）和日循环热路径精简的性能优化要求

### Modified Capabilities
（无 spec 级行为变更，所有优化均为内部实现改进，不改变输入输出协议）

## Impact

- **直接修改文件**：
  - `backend/core/engine_vector/features.py` — 特征矩阵计算（rolling/ewm/ATR）
  - `backend/core/engine_vector/data_matrix.py` — OHLC 矩阵构建
  - `backend/core/engine_vector/portfolio_simulator_strict.py` — `_build_price_indices` + `_run_unified_loop`
  - `backend/core/engine_vector/sma_signal_provider.py` — `day_signals` 行切片/debug guard/multifactor 预计算
- **间接影响**：回测结果必须与 Phase 4 基线 100% 数值一致（zero diff 回归验证）
- **无 API/前端变更**：纯内部实现优化，不改变任何外部接口
