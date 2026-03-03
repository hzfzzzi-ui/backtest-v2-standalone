## 1. SMA 路径：删除冗余字段

- [x] 1.1 删除 SMA 路径 daily_row 初始化中的 `positions_count_end_of_day`（L483）、`buy_slots_after_sell`（L494）、`buy_slots_calculated`（L503）、`candidates_after_held_filter_count`（L504）
- [x] 1.2 删除 SMA 路径日末赋值中对 `buy_slots_after_sell`（L526, L869）、`buy_slots_calculated`（L527, L878）、`candidates_after_held_filter_count`（L879）的写入

## 2. Generic 路径：补齐卖出漏斗

- [x] 2.1 在 Generic 路径 daily_row 初始化中添加 `positions_before_sell`、`sells_executed_count`、`positions_after_sell` 字段（默认 0）
- [x] 2.2 在 Generic 路径退出规则处理后（策略信号过滤后），计算并回填实际的 `positions_before_sell`、`sells_executed_count`、`positions_after_sell`

## 3. Generic 路径：补齐买入漏斗

- [x] 3.1 在 Generic 路径 daily_row 初始化中添加 `raw_buy_signal_count`、`after_held_filter_count`、`after_slot_filter_count`、`after_cash_lot_count` 字段（默认 0）
- [x] 3.2 在 Generic 路径信号处理和订单构建后，从策略信号列表和 `debug_plan` 中提取实际的买入漏斗计数并回填

## 4. Generic 路径：补齐遗漏的通用字段

- [x] 4.1 在 Generic 路径 daily_row 初始化中添加 SMA 路径已有但 Generic 缺失的通用字段：`sorting_triggered`（默认 False）、`strong_risk_on`（默认 0）、`buy_candidate_count`（默认 0）
- [x] 4.2 在 Generic 路径对应位置回填这些字段的实际值

## 5. 验证

- [x] 5.1 Docker 重建后端并运行 SMA 策略回测，确认 `portfolio_daily.csv` 不含被删除的 4 个冗余列，且其余字段值正确
- [x] 5.2 运行 Generic 路径（EMA_CROSS）策略回测，确认 `portfolio_daily.csv` 包含完整的卖出漏斗和买入漏斗字段，值非全零
