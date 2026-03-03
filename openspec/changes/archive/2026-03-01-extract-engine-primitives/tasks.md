## 1. 提取 `_build_price_indices`

- [x] 1.1 在 `portfolio_simulator_strict.py` 中定义 `_build_price_indices(raw_df: pd.DataFrame) -> tuple[dict, dict]` 函数，从 DataFrame 构建 open_idx 和 close_idx
- [x] 1.2 SMA 路径（L299-311）替换为调用 `_build_price_indices()`
- [x] 1.3 Generic 路径（L1209-1221）替换为调用 `_build_price_indices()`

## 2. 提取 `_process_pending_fills`

- [x] 2.1 在 `portfolio_simulator_strict.py` 中定义 `_process_pending_fills()` 函数，包含完整的 SELL/BUY 成交逻辑、trade_row 构建、状态更新
- [x] 2.2 SMA 路径日循环中的订单成交代码（L375-455）替换为调用 `_process_pending_fills()`，传入 SMA 特有的状态字典
- [x] 2.3 Generic 路径日循环中的订单成交代码（L1327-1404）替换为调用 `_process_pending_fills()`，传入 Generic 特有的状态字典

## 3. 验证

- [x] 3.1 Docker 重建并运行 SMA 回测，对比提取前后 portfolio_daily.csv 和 portfolio_trades.csv 数值一致
- [x] 3.2 运行 Generic（EMA_CROSS）回测，对比提取前后数值一致
