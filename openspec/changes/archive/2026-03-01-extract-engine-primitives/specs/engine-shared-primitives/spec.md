## ADDED Requirements

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
