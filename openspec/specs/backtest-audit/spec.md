## ADDED Requirements

### Requirement: 审计产物输出
系统 SHALL 在每次回测完成后输出 `audit.json` 到实验目录，包含恒等式检查汇总和异常日详情。

#### Scenario: audit.json 正常生成
- **WHEN** 一次回测实验成功完成并通过 stabilize 阶段
- **THEN** 实验目录 SHALL 包含 `audit.json` 文件
- **THEN** manifest.json 的 artifacts 字段 SHALL 包含 `"audit": "audit.json"`

#### Scenario: audit.json 生成失败不阻塞回测
- **WHEN** 审计数据收集或写入过程中发生异常
- **THEN** 系统 SHALL 记录错误日志，但不影响回测结果的正常返回
- **THEN** manifest.json 的 artifacts 字段 SHALL 包含 `"audit": null`

---

### Requirement: 现金守恒检查
系统 SHALL 在每个交易日的 fill 执行后验证现金守恒恒等式。

#### Scenario: 无成交日
- **WHEN** 某交易日无 pending 订单需要执行
- **THEN** cash_after SHALL 等于 cash_before（差值为 0）
- **THEN** cash_check SHALL 为 true

#### Scenario: 有成交日（卖出）
- **WHEN** 某交易日执行了卖出成交，fill_net = gross - commission - stamp_tax
- **THEN** cash_after SHALL 等于 cash_before + Σ(sell_net)
- **THEN** cash_check SHALL 为 true

#### Scenario: 有成交日（买入）
- **WHEN** 某交易日执行了买入成交，fill_net = gross + commission
- **THEN** cash_after SHALL 等于 cash_before - Σ(buy_net)
- **THEN** cash_check SHALL 为 true

#### Scenario: 混合成交日
- **WHEN** 某交易日同时有买入和卖出成交
- **THEN** cash_after SHALL 等于 cash_before + Σ(sell_net) - Σ(buy_net)
- **THEN** cash_check SHALL 为 true

---

### Requirement: 持仓守恒检查
系统 SHALL 在每个交易日的 fill 执行后验证持仓守恒恒等式。

#### Scenario: 持仓数量守恒
- **WHEN** 某交易日执行了 B 笔买入（新增持仓标的）和 S 笔卖出（清仓标的）
- **THEN** positions_after SHALL 等于 positions_before + new_entries - full_exits
- **THEN** pos_check SHALL 为 true

#### Scenario: 单标的数量守恒
- **WHEN** 某标的在某交易日执行了买入 qty_buy 或卖出 qty_sell
- **THEN** 该标的的 position_after SHALL 等于 position_before + qty_buy - qty_sell

---

### Requirement: NAV 一致性检查
系统 SHALL 在每个交易日的 NAV 快照后验证 NAV 等于现金加市值。

#### Scenario: NAV 恒等式
- **WHEN** 某交易日计算 NAV 快照
- **THEN** nav SHALL 等于 cash + Σ(positions[i] × close[i])（容差 0.01 元）
- **THEN** nav_check SHALL 为 true

#### Scenario: NAV 非 NaN
- **WHEN** 某交易日计算 NAV 快照
- **THEN** nav SHALL 不为 NaN 且不为负数

---

### Requirement: T+1 执行验证
系统 SHALL 验证所有信号遵循 T+1 执行规则（信号日产生，次日成交）。

#### Scenario: 信号次日执行
- **WHEN** 某交易日产生 N 个信号并构建订单
- **THEN** 订单 SHALL 排入 pending[next_trading_day]，不在信号日当天执行
- **THEN** t1_check SHALL 为 true

#### Scenario: 全周期无违规
- **WHEN** 回测完成
- **THEN** audit_summary.t1_check_fail SHALL 为 0

---

### Requirement: 成交价格合理性检查
系统 SHALL 记录每笔成交的价格合理性指标，用于外部审查。

#### Scenario: 滑点一致性
- **WHEN** 某笔买入成交，配置 slippage_bps = 2
- **THEN** fill_price SHALL 等于 open_price × (1 + 0.0002)（容差 0.01）
- **THEN** 记录的 slip_bps SHALL 等于配置的 slippage_bps

#### Scenario: 跳空记录
- **WHEN** 某笔成交的信号日收盘价为 signal_close，成交日开盘价为 fill_open
- **THEN** gap_pct SHALL 等于 (fill_open - signal_close) / signal_close × 100

#### Scenario: 跳空分布汇总
- **WHEN** 回测完成
- **THEN** audit_summary SHALL 包含 fill_gap_pct 的 P50、P95、Max 统计值

---

### Requirement: 成本审计
系统 SHALL 汇总全周期的交易成本明细。

#### Scenario: 成本汇总
- **WHEN** 回测完成
- **THEN** audit_summary SHALL 包含 total_commission、total_stamp_tax、total_slippage 字段
- **THEN** audit_summary SHALL 包含 cost_as_pct_of_initial（总成本占初始资金比例）

#### Scenario: 成本参数记录
- **WHEN** 回测完成
- **THEN** audit_summary SHALL 包含 cost_config 字段，记录实际使用的 commission_rate、commission_min、stamp_tax_rate、slippage_bps

---

### Requirement: 数据质量检查点
系统 SHALL 在仿真循环开始前检查输入数据的质量。

#### Scenario: 价格矩阵 NaN 统计
- **WHEN** 数据加载完成
- **THEN** audit_summary.data_quality SHALL 包含 close_nan_rate（收盘价 NaN 比例）和 open_nan_rate（开盘价 NaN 比例）

#### Scenario: 日期连续性
- **WHEN** 数据加载完成
- **THEN** audit_summary.data_quality SHALL 包含 trading_days_count 和 date_gaps（交易日历缺口数）

#### Scenario: 标的覆盖
- **WHEN** 数据加载完成
- **THEN** audit_summary.data_quality SHALL 包含 symbols_count（标的数量）和 symbols_with_full_coverage（全周期有数据的标的数）

---

### Requirement: 可疑模式自动检测
系统 SHALL 自动检测并标记可疑的回测行为模式。

#### Scenario: 涨跌停成交
- **WHEN** 某笔成交的 fill_open 相对 signal_close 的跳空幅度 ≥ 9.5%
- **THEN** flags 数组 SHALL 包含一条 WARNING 级别记录，标注日期、标的、跳空幅度

#### Scenario: 现金负值
- **WHEN** 任意交易日的 cash < 0
- **THEN** flags 数组 SHALL 包含一条 ERROR 级别记录

#### Scenario: 持仓超限
- **WHEN** 任意交易日的 positions_count > max_positions
- **THEN** flags 数组 SHALL 包含一条 ERROR 级别记录

#### Scenario: NAV 异常
- **WHEN** 任意交易日的 nav 为 NaN 或为负数
- **THEN** flags 数组 SHALL 包含一条 ERROR 级别记录

#### Scenario: 策略僵死
- **WHEN** 连续 20 个交易日以上无任何信号产生且有持仓
- **THEN** flags 数组 SHALL 包含一条 WARNING 级别记录

#### Scenario: 单日全换手
- **WHEN** 某交易日的 turnover_pct > 100%
- **THEN** flags 数组 SHALL 包含一条 WARNING 级别记录

#### Scenario: 孤立成交
- **WHEN** 某笔成交的 reason_code 为空字符串
- **THEN** flags 数组 SHALL 包含一条 WARNING 级别记录

#### Scenario: 标记数量上限
- **WHEN** flags 数组超过 50 条
- **THEN** 系统 SHALL 截断并在末尾追加一条 `"... and N more flags truncated"` 记录

---

### Requirement: audit.json 输出格式
audit.json SHALL 遵循固定 schema，便于机器解析。

#### Scenario: 顶层结构
- **WHEN** audit.json 生成
- **THEN** 顶层 SHALL 包含 `version`（"1.0"）、`exp_id`、`generated_at`（ISO 时间戳）、`summary`、`data_quality`、`flagged_days`、`flags` 字段

#### Scenario: summary 结构
- **WHEN** audit.json 生成
- **THEN** summary SHALL 包含：`trading_days_count`、`cash_check_pass`/`cash_check_fail`、`pos_check_pass`/`pos_check_fail`、`nav_check_pass`/`nav_check_fail`、`t1_check_pass`/`t1_check_fail`、`total_fills`、`total_signals`、`orphan_fills`、`fill_gap_pct_p50`/`p95`/`max`、`total_commission`/`total_stamp_tax`/`total_slippage`、`cost_as_pct_of_initial`、`cost_config`

#### Scenario: flagged_days 结构
- **WHEN** 某交易日的任一检查失败或有异常成交
- **THEN** flagged_days 数组 SHALL 包含该日的完整审计记录：`date`、`cash_before`/`cash_after`/`fills_net`/`costs_total`/`cash_check`、`positions_before`/`positions_after`/`buys_filled`/`sells_filled`/`pos_check`、`nav`/`cash`/`market_value`/`nav_check`、`signals_generated`/`orders_scheduled`/`fills_from_yesterday`/`t1_check`、`fills`（含 sym/side/signal_close/fill_open/fill_price/gap_pct/slip_bps）
