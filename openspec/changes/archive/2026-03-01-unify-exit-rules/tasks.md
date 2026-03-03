## 1. 定义 `_evaluate_engine_exits` 函数

- [x] 1.1 在 `portfolio_simulator_strict.py` 中定义 `ExitCounts` dataclass 和 `_evaluate_engine_exits()` 函数，实现 6 条引擎级退出规则（RISK_OFF > ATR_STOP > FIXED_STOP > TAKE_PROFIT > ATR_TRAIL > TIME_EXIT），按设计文档签名

## 2. SMA 路径

- [x] 2.1 SMA 路径保持内联退出逻辑不变（TREND_BREAK 优先级交错 + 富 meta + 双峰值状态 + break_streak 使提取不实际，Phase 4 统一引擎循环时一并解决）

## 3. Generic 路径替换

- [x] 3.1 Generic 路径新增 benchmark regime 标量查询（risk_on bool），从已有 benchmark DataFrame 派生
- [x] 3.2 Generic 路径退出判断代码替换为调用 `_evaluate_engine_exits()`，构造 `get_atr` lambda 从 `_atr_lookup2` dict 查询，补齐 RISK_OFF_EXIT 和 TIME_EXIT

## 4. 验证

- [x] 4.1 Docker 重建并运行 SMA 回测，对比提取前后 portfolio_daily.csv 和 portfolio_trades.csv 数值一致
- [x] 4.2 运行 Generic（EMA_CROSS）回测，对比提取前后数值一致（当前配置下 RISK_OFF 和 TIME_EXIT 未启用，结果应不变）
