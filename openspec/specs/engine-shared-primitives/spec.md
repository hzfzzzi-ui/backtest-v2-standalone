# engine-shared-primitives Specification

## Purpose

定义多条运行路径共享的成交处理与价格索引基础函数，减少重复实现并统一核心原语行为。

## Requirements

### Requirement: 订单成交处理函数
引擎 SHALL 提供共享函数 `_process_pending_fills()` 处理待执行订单的成交逻辑。该函数 MUST：
- 接收待执行订单列表、当日开盘价索引、成本参数（滑点/佣金/印花税）、当前仓位、当前现金、仓位均价、以及需要在清仓时清理的可选状态字典列表
- 对每笔 SELL 订单：计算滑点调整后成交价、佣金、印花税、净额，更新仓位和现金；清仓时清理所有传入的状态字典
- 对每笔 BUY 订单：计算滑点调整后成交价、佣金、净额，检查现金充足性，更新仓位、均价和现金
- 返回更新后的现金、成交额、生成的 trade_row 列表
- 函数 MUST NOT 修改传入订单列表本身

#### Scenario: 卖出订单成交
- **WHEN** 待执行订单包含一笔 SELL 订单，持仓足够，开盘价有效
- **THEN** 成交价 = 开盘价 × (1 - slippage_bps/10000)，佣金 = max(commission_min, gross × commission_rate)，印花税 = gross × stamp_tax_rate，现金增加 net = gross - commission - stamp_tax，仓位减少对应数量

#### Scenario: 卖出清仓时清理状态
- **WHEN** 卖出后该标的仓位降至 0
- **THEN** 从 positions、position_avg_cost 及所有传入的额外状态字典中删除该标的的 key

#### Scenario: 买入订单成交
- **WHEN** 待执行订单包含一笔 BUY 订单，现金充足，开盘价有效
- **THEN** 成交价 = 开盘价 × (1 + slippage_bps/10000)，佣金 = max(commission_min, gross × commission_rate)，现金减少 net = gross + commission，仓位和均价按加权平均更新

#### Scenario: 现金不足跳过买入
- **WHEN** 买入所需 net 金额超过可用现金
- **THEN** 跳过该订单，不产生 trade_row，现金和仓位不变

---

### Requirement: 价格索引构建函数
引擎 SHALL 提供共享函数 `_build_price_indices()` 从原始价格 DataFrame 构建 (date, symbol) → price 的字典索引。该函数 MUST：
- 接收原始价格 DataFrame（含 date, symbol, open, close 列）
- 返回 `open_idx` 和 `close_idx` 两个 dict[tuple[date, str], float]
- symbol MUST 统一转为小写

#### Scenario: 从 DataFrame 构建索引
- **WHEN** 传入包含 N 个交易日 × M 个标的的价格 DataFrame
- **THEN** 返回的 open_idx 和 close_idx 各包含 N×M 个 (date, symbol) → float 键值对

#### Scenario: 两路径使用同一函数
- **WHEN** SMA 路径和 Generic 路径分别调用 `_build_price_indices()`
- **THEN** 返回结构相同的索引字典，与各自原有内联代码产生完全相同的结果

---

### Requirement: 引擎退出规则评估函数
引擎 SHALL 提供共享函数 `_evaluate_engine_exits()` 评估所有持仓的引擎级退出规则。该函数 MUST：
- 接收当前持仓列表、当日日期、收盘价索引、均价字典、ATR 查询函数、峰值状态字典、入场日字典、退出配置（ExitConfig）、以及可选的 risk_on 标志和 max_hold_days
- 按优先级顺序评估退出规则：RISK_OFF > ATR_STOP > FIXED_STOP > TAKE_PROFIT > ATR_TRAIL > TIME_EXIT
- 每个标的最多触发一条退出信号（命中最高优先级规则后跳过后续规则）
- 更新峰值状态（原地修改）
- 返回退出信号列表和各规则触发计数
- 函数 MUST NOT 包含策略层退出逻辑（如 TREND_BREAK_EXIT、CROSS_DOWN），这些属于信号提供者职责

#### Scenario: RISK_OFF 退出
- **WHEN** risk_on 为 False 且持仓存在
- **THEN** 对所有持仓生成 RISK_OFF_EXIT 信号，优先级最高

#### Scenario: ATR_STOP_LOSS 退出
- **WHEN** enable_atr_stop 为 True，ATR 值有效，收盘价 ≤ 均价 - atr_stop_k × ATR
- **THEN** 生成 ATR_STOP_LOSS 信号，atr_stop_exit_count 加 1

#### Scenario: FIXED_STOP_LOSS 退出
- **WHEN** enable_fixed_stop_loss 为 True，均价 > 0，收盘价 ≤ 均价 × (1 - fixed_stop_loss_pct)
- **THEN** 生成 FIXED_STOP_LOSS 信号，fixed_stop_loss_exit_count 加 1

#### Scenario: TAKE_PROFIT 退出
- **WHEN** enable_take_profit 为 True，均价 > 0，且满足止盈条件（pct 模式或 atr 模式）
- **THEN** 生成 TAKE_PROFIT 信号，take_profit_exit_count 加 1

#### Scenario: ATR_TRAIL_EXIT 退出
- **WHEN** enable_atr_trail 为 True，ATR 值有效，收盘价 ≤ 峰值 - atr_trail_k × ATR
- **THEN** 生成 ATR_TRAIL_EXIT 信号，atr_trail_exit_count 加 1

#### Scenario: TIME_EXIT 退出
- **WHEN** max_hold_days > 0，标的在 entry_day 中有记录，持仓天数 ≥ max_hold_days
- **THEN** 生成 TIME_EXIT 信号

#### Scenario: 峰值状态更新
- **WHEN** 评估某标的退出规则时
- **THEN** 峰值状态更新为 max(当前峰值, 当日收盘价)，无论是否触发退出

#### Scenario: 两路径使用同一函数
- **WHEN** SMA 路径和 Generic 路径分别调用 `_evaluate_engine_exits()`
- **THEN** 引擎级退出规则的判断结果完全一致；SMA 路径的 TREND_BREAK_EXIT 和 CROSS_DOWN 在调用方处理
