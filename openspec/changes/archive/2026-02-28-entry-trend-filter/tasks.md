## 1. 策略参数扩展

- [x] 1.1 `ema_cross.py`: 在 `EMACrossStrategy` dataclass 新增 `enable_entry_above_slow_ma: bool = False`、`enable_entry_slow_ma_slope: bool = False`、`entry_slope_lookback: int = 5` 三个字段
  - DoD: dataclass 可实例化，默认值正确
  - 验证: `EMACrossStrategy()` 实例化后属性存在且默认关闭

- [x] 1.2 `registry.py`: 在 `ema_cross` 分支透传三个新参数到 `EMACrossStrategy()` 构造
  - DoD: `build_strategy(cfg)` 可正确读取 params 中的新字段
  - 验证: 构造后策略实例的属性值与 params 一致

## 2. 信号矩阵计算

- [x] 2.1 `signal_matrix.py`: `build_signal_matrices()` 新增 `enable_entry_above_slow_ma`、`enable_entry_slow_ma_slope`、`entry_slope_lookback` 参数，计算两个布尔矩阵
  - `entry_above_slow_ma`: `close > slow_ma`（逐元素比较，NaN 位置为 False）
  - `entry_slow_ma_slope_pos`: `slow_ma[lb:] - slow_ma[:-lb] > 0`（前 lb 行为 False）
  - 禁用时返回全 True 矩阵（不影响后续 AND）
  - DoD: 返回字典新增两个 key，shape 为 (t, n)
  - 验证: 构造 3x2 的 close/slow_ma 测试矩阵，验证输出正确

- [x] 2.2 `portfolio_simulator_strict.py`: 从策略 getattr 读取三个新参数，传递给 `build_signal_matrices()` 调用
  - DoD: `build_signal_matrices()` 调用包含新参数
  - 验证: 回测不报错，默认参数下行为不变

## 3. 引擎买入过滤集成

- [x] 3.1 `portfolio_simulator_strict.py`: 在 `raw_buy_mask` 组装后，条件性 AND 两个入场过滤矩阵
  - 仅在对应 enable 参数为 true 时应用
  - DoD: `raw_buy_mask` 在启用时额外 AND 入场过滤矩阵
  - 验证: 启用 `enable_entry_above_slow_ma=true` 后，`buy_candidate_count` 应小于等于未启用时

- [x] 3.2 诊断计数器: 在每日循环中统计 `entry_above_slow_ma_block_count` 和 `entry_slope_block_count`，写入 metrics
  - 统计方式: 原始 mask（cross_up & buffer_ok & trend_ok & risk_on & ma_is_valid）通过但被入场过滤阻断的信号数
  - DoD: metrics dict 包含两个计数器
  - 验证: `run_meta.json` counters 中可见新计数器

- [x] 3.3 信号 meta 扩展: 在买入候选的 `day_gate_by_symbol` 和信号 meta 中增加 `entry_above_slow_ma` 和 `slow_ma_slope_pos` 布尔字段
  - DoD: trades CSV 的 meta_json 包含新字段
  - 验证: 导出 trades.csv，meta_json 中有 `entry_above_slow_ma` 字段

## 4. 前端 UI

- [x] 4.1 `index.html`: 在 Signal Generation 区域 MA 参数下方新增"入场趋势过滤"子区域
  - checkbox: `close > slow_ma`（id: `entryAboveSlowMa`）
  - checkbox: `slow_ma 斜率 > 0`（id: `entrySlowMaSlope`）
  - 数字输入: `斜率回看天数`（id: `entrySlopeLookback`，默认 5，仅在斜率 checkbox 启用时可编辑）
  - DoD: UI 渲染正确，控件交互正常
  - 验证: 浏览器打开页面，可见新控件

- [x] 4.2 `backtest_v2.js`: 收集三个新参数并传递给后端 API
  - 在参数收集函数中读取 checkbox 和 input 值
  - 传入 `strategy.params` 中
  - DoD: 后端收到请求包含新参数
  - 验证: 浏览器 Network 面板检查请求 payload

## 5. 实验配置与对比回测

- [x] 5.1 新建 `configs/plan_a_ema_cross_entry_filter.json`: 基于 `plan_a_ema_cross.json`，额外启用两个入场过滤
  - `enable_entry_above_slow_ma: true`
  - `enable_entry_slow_ma_slope: true`
  - `entry_slope_lookback: 5`
  - 其他参数与最近一次回测保持一致
  - DoD: 配置文件 JSON 合法，包含新参数
  - 验证: `python -m json.tool` 校验无错

- [x] 5.2 运行对比回测: 分别使用 `plan_a_ema_cross.json`（无过滤）和 `plan_a_ema_cross_entry_filter.json`（有过滤）运行回测
  - 对比: total_return、max_drawdown、sharpe、trade_count
  - 验证 `entry_above_slow_ma_block_count > 0` 且 `entry_slope_block_count > 0`
  - DoD: 两组回测均成功完成，过滤组的 block 计数器 > 0
  - 验证: 前端可加载两组结果，诊断数据可见

## 6. Docker 构建验证

- [x] 6.1 Docker 重新构建并启动，前端完整测试
  - 构建: `docker-compose build backend && docker-compose up -d`
  - 测试: 前端勾选入场过滤 → 运行回测 → 查看 trades 表和诊断面板
  - DoD: 前端可正常使用入场过滤功能，结果与 CLI 回测一致
  - 验证: 前端 trades 表显示正常，诊断计数器有值
