## ADDED Requirements

### Requirement: EMA 均线交叉信号计算
VECTOR 引擎 SHALL 支持 EMA 类型的均线交叉信号，与现有 SMA 并列。

#### Scenario: EMA 策略信号生成
- **WHEN** 配置 `strategy.name = "ema_cross"` 且引擎执行 SMA 路径
- **THEN** `fast_ma` 和 `slow_ma` SHALL 使用 `ewm(span=fast/slow).mean()` 计算
- **THEN** 金叉/死叉判定逻辑与 SMA 路径相同（fast_ma 上穿/下穿 slow_ma）

#### Scenario: SMA 策略行为不变
- **WHEN** 配置 `strategy.name = "sma_cross"` 或其他非 EMA 策略
- **THEN** `fast_ma` 和 `slow_ma` SHALL 继续使用 `rolling(window).mean()` 计算
- **THEN** 行为与变更前完全一致

#### Scenario: ma_type 可观测
- **WHEN** 回测完成
- **THEN** `run_meta.json` 或 `audit.json` SHALL 记录实际使用的 `ma_type`（`"EMA"` 或 `"SMA"`）

---

### Requirement: 固定金额 sizing 模式
VECTOR 引擎 SHALL 支持以固定金额作为每仓目标，替代默认的 `NAV / max_positions` sizing。

#### Scenario: 指定 base_order_value
- **WHEN** 配置 `sizing.order_value > 0`（例如 30000）
- **THEN** 每笔买入订单的 target_amount SHALL 等于 `sizing.order_value`
- **THEN** 最终数量 SHALL 为 `floor(target_amount / fill_price) // lot_size * lot_size`

#### Scenario: 现金不足时跳过
- **WHEN** `base_order_value` 对应的订单金额超过可用现金
- **THEN** 该笔买入 SHALL 被跳过（现有 `if net > cash: continue` 逻辑）
- **THEN** 实际持仓数量低于 `max_positions`

#### Scenario: 未指定 base_order_value 时回退
- **WHEN** 配置未指定 `sizing.order_value` 或其值 ≤ 0
- **THEN** target_amount SHALL 回退到 `NAV / max_positions`（现有行为）

---

### Requirement: 方案 A 实验配置
系统 SHALL 提供一个可直接运行的方案 A 配置文件。

#### Scenario: 配置参数完整
- **WHEN** 使用 `configs/plan_a_ema_cross.json` 运行回测
- **THEN** 以下参数 SHALL 生效：
  - `strategy.name = "ema_cross"`，`fast = 8`，`slow = 55`
  - `max_positions = 6`
  - `sizing.order_value = 30000`
  - `execution.lot_size = 100`
  - `universe_mode = "ALL_A"`，`universe_limit = 800`
  - `initial_capital = 100000`

#### Scenario: 参数可验证
- **WHEN** 回测完成
- **THEN** `audit.json` 中 `cost_config` 字段 SHALL 反映实际成本参数
- **THEN** trades CSV 中 `commission` 列的值 SHALL 大于等于 5.0（最低佣金）
- **THEN** 大部分成交的佣金 SHALL 接近 `金额 × 0.0003`（而非被最低佣金主导）

---

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
