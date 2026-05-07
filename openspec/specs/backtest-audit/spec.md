# backtest-audit Specification

## Purpose
定义回测审计产物、恒等式校验、T+1 执行验证，以及多 alpha 组合场景下的组合与归因审计要求。
## Requirements
### Requirement: 审计产物输出
系统 SHALL 在每次回测完成后输出 `audit.json` 到实验目录，包含恒等式检查汇总和异常日详情。

#### Scenario: audit.json 正常生成
- **WHEN** 一次回测实验成功完成并通过 stabilize 阶段
- **THEN** 实验目录 SHALL 包含 `audit.json` 文件
- **THEN** manifest.json 的 artifacts 字段 SHALL 包含 `"audit": "audit.json"`

#### Scenario: audit.json 生成失败不阻塞回测
- **WHEN** 审计数据收集或写入过程中发生异常
- **THEN** 系统 SHALL 记录错误日志，但不影响回测结果的正常返回
- **THEN** manifest.json 的 artifacts 字段 SHALL 包含 `"audit": null"`

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

### Requirement: 持仓守恒检查
系统 SHALL 在每个交易日的 fill 执行后验证持仓守恒恒等式。

#### Scenario: 持仓数量守恒
- **WHEN** 某交易日执行了 B 笔买入（新增持仓标的）和 S 笔卖出（清仓标的）
- **THEN** positions_after SHALL 等于 positions_before + new_entries - full_exits
- **THEN** pos_check SHALL 为 true

#### Scenario: 单标的数量守恒
- **WHEN** 某标的在某交易日执行了买入 qty_buy 或卖出 qty_sell
- **THEN** 该标的的 position_after SHALL 等于 position_before + qty_buy - qty_sell

### Requirement: NAV 一致性检查
系统 SHALL 在每个交易日的 NAV 快照后验证正式 NAV 等式；当 `pay_date` 口径下存在分红应收时，NAV 必须显式纳入 `dividend_receivable`。

#### Scenario: 无分红应收时 NAV 等式
- **WHEN** 某交易日不存在 `dividend_receivable`
- **THEN** `nav` SHALL 等于 `cash + market_value`（容差 0.01 元）
- **THEN** `nav_check` SHALL 为 `true`

#### Scenario: 存在分红应收时 NAV 等式
- **WHEN** 某交易日存在 `dividend_receivable`
- **THEN** `nav` SHALL 等于 `cash + dividend_receivable + market_value`（容差 0.01 元）
- **THEN** `nav_check` SHALL 为 `true`

#### Scenario: NAV 非 NaN
- **WHEN** 某交易日计算 NAV 快照
- **THEN** `nav` SHALL 不为 NaN 且不为负数

### Requirement: T+1 执行验证
系统 SHALL 验证所有原始 alpha 信号、组合后信号和最终订单都遵循 T+1 执行规则（`t` 日信号形成，`t+1` 日成交）。

#### Scenario: 组合后信号次日执行
- **WHEN** 某交易日生成 `raw_alpha_signals` 与 `composed_buy_signals`
- **THEN** 基于这些信号生成的订单 SHALL 排入 `pending[next_trading_day]`
- **THEN** 系统 SHALL 不在信号日当天执行这些订单

#### Scenario: 全周期无违规
- **WHEN** 回测完成
- **THEN** `audit_summary.t1_check_fail` SHALL 为 `0`

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

### Requirement: 成本审计
系统 SHALL 汇总全周期的交易成本明细。

#### Scenario: 成本汇总
- **WHEN** 回测完成
- **THEN** audit_summary SHALL 包含 total_commission、total_stamp_tax、total_slippage 字段
- **THEN** audit_summary SHALL 包含 cost_as_pct_of_initial（总成本占初始资金比例）

#### Scenario: 成本参数记录
- **WHEN** 回测完成
- **THEN** audit_summary SHALL 包含 cost_config 字段，记录实际使用的 commission_rate、commission_min、stamp_tax_rate、slippage_bps

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

### Requirement: audit.json 输出格式
`audit.json` SHALL 遵循固定 schema，便于机器解析，并在多 alpha 组合场景下扩展组合与归因字段。

#### Scenario: 顶层结构
- **WHEN** `audit.json` 生成
- **THEN** 顶层 SHALL 包含 `version`、`exp_id`、`generated_at`、`summary`、`data_quality`、`flagged_days`、`flags` 字段

#### Scenario: summary 结构
- **WHEN** `audit.json` 生成
- **THEN** `summary` SHALL 继续包含现有审计统计字段
- **THEN** `summary` SHALL 额外包含 `raw_signal_counts_by_alpha`、`composed_signal_counts_by_alpha`、`blocked_signal_counts_by_reason`、`conflict_resolution_counts`、`source_only_exit_count`、`global_risk_override_count`

#### Scenario: flagged_days 结构
- **WHEN** 某交易日的任一检查失败、发生组合冲突或出现来源感知退出
- **THEN** `flagged_days` SHALL 包含该日的完整审计记录
- **THEN** 该记录 SHALL 能表示 `raw_alpha_signals`、`composed_buy_signals`、`composed_sell_signals`、`same_symbol_conflicts`、`source_exit_count`、`global_risk_override_count`

### Requirement: 组合层审计输出
系统 SHALL 为多 alpha 组合输出最小可验证的审计统计，至少覆盖“组合前”“组合后”“冲突裁决后”三个层面。

#### Scenario: 原始信号与组合后信号计数
- **WHEN** 某交易日启用多 alpha 组合
- **THEN** 审计输出 SHALL 记录每个 `alpha_id` 的原始信号数量
- **THEN** 审计输出 SHALL 记录每个 `alpha_id` 的组合后放行数量

#### Scenario: 同股冲突裁决被审计
- **WHEN** 某交易日某标的发生同股冲突裁决
- **THEN** 审计输出 SHALL 记录冲突涉及的 `alpha_id`、被放行的策略和裁决原因

### Requirement: 来源退出审计输出
系统 SHALL 区分“来源策略退出”和“全局风险覆盖退出”，并在审计结果中分别统计。

#### Scenario: 来源策略退出被记录
- **WHEN** 某持仓因其 `entry_alpha_id` 对应的 `S9` 规则而退出
- **THEN** 审计输出 SHALL 记录该笔退出属于 `source_only`
- **THEN** 退出统计 SHALL 归入对应 `alpha_id`

#### Scenario: 全局风险覆盖退出被记录
- **WHEN** 某持仓因 `S8` 的全局风险规则而被强平
- **THEN** 审计输出 SHALL 记录该笔退出属于 `global_risk_override`
- **THEN** 该笔退出 SHALL 不计入任意来源策略的正常退出次数

### Requirement: audit.json 必须兼容 research_audit 子树
系统 MUST 在保留现有 execution audit trail 的前提下，允许 `audit.json` 承载 `research_audit` 子树。

#### Scenario: execution audit 与 research audit 共存
- **WHEN** 一次实验同时生成 execution audit trail 和 research audit
- **THEN** `audit.json` SHALL 同时保留现有 execution audit 字段
- **THEN** `audit.json` SHALL 追加 `research_audit` 子树
- **THEN** 系统 SHALL NOT 因追加 `research_audit` 而删除既有 `stage_pipeline`、`warnings` 或其他已存在的 execution audit 字段

#### Scenario: research audit 生成失败不破坏 execution audit
- **WHEN** research audit 的生成过程发生异常
- **THEN** 系统 SHALL 优先保留现有 execution audit 内容
- **THEN** 系统 SHALL 记录 research audit 的错误日志，而不是破坏既有 `audit.json` 写盘流程

### Requirement: research_audit 不得重复存储已有审计产物
系统 MUST 让 `research_audit` 引用现有 artifact 作为证据，而不是复制 `run_meta`、`stage_summary`、`manifest` 的完整内容。

#### Scenario: 引用 stage 与实验元信息
- **WHEN** `research_audit` 需要引用 stage 执行信息或实验元信息
- **THEN** `research_audit` SHALL 通过 `evidence_refs` 或精简 `evidence` 字段引用 `run_meta.json`、`stage_summary.json`、`manifest.json`
- **THEN** `research_audit` SHALL NOT 内嵌这些文件的完整 payload

#### Scenario: 复用已有审计摘要
- **WHEN** `research_audit` 需要表达 execution shell、stage 顺序或警告摘要
- **THEN** 系统 SHALL 优先复用现有 `stage_pipeline`、`stage_summary` 和 execution audit 内容
- **THEN** 系统 SHALL NOT 再定义第二套等价字段保存同一事实

### Requirement: audit.json 必须暴露 execution lineage 摘要与异常样本
系统 MUST 在现有 execution audit 结构中新增 execution lineage 摘要，至少覆盖生成信号数、排程订单数、成交数、终止数以及 dropped/missing/same-day 等异常计数。

#### Scenario: lineage 摘要写入 audit.json
- **WHEN** 一次实验完成并具备 lineage ledger 产物
- **THEN** `audit.json` SHALL 输出 execution lineage 摘要
- **THEN** `audit.json` SHALL 同时提供台账引用和受控异常样本

#### Scenario: 发现链路异常
- **WHEN** 某次实验存在 same-day fill、已生成但未排程、已排程但无终态或等价链路异常
- **THEN** execution audit SHALL 记录对应异常计数
- **THEN** 主审计文件 SHALL 保留受控样本供人工复核

### Requirement: lineage 明细不得污染主审计文件
系统 SHALL NOT 在 `audit.json` 中内联全量生命周期台账。

系统 SHALL NOT 在 `audit.json` 中内联全量生命周期台账。

#### Scenario: 明细留在独立 artifact
- **WHEN** 某次实验的订单和成交数量较多
- **THEN** `audit.json` SHALL 仍保持摘要级结构
- **THEN** 全量 lineage 明细 SHALL 留在独立 ledger artifact 中### Requirement: audit.json 必须承接主线会计完整性摘要
系统 MUST 在现有 `audit.json` execution audit 结构中承接主线 `accounting_integrity` 审计摘要，使其与 `stage_pipeline`、`warnings` 和既有 execution audit 字段共存。

系统 MUST 在现有 `audit.json` execution audit 结构中承接主线 `accounting_integrity` 审计摘要，使其与 `stage_pipeline`、`warnings` 和既有 execution audit 字段共存。

#### Scenario: execution audit 与 accounting_integrity 共存
- **WHEN** 一次实验通过标准 stabilize 流程写入 `audit.json`
- **THEN** `audit.json` SHALL 同时保留现有 `stage_pipeline`、`warnings` 和 `days_with_fills` 等字段
- **THEN** `audit.json` SHALL 额外包含 `accounting_integrity` 子树或等价 execution audit 摘要字段

#### Scenario: 证据不足时保留审计结果
- **WHEN** 当前正式执行路径未提供足够的会计快照证据
- **THEN** `audit.json` SHALL 仍然正常写盘
- **THEN** `accounting_integrity` SHALL 以 `UNKNOWN` 或等价状态表达证据不足，而不是缺失整份审计文件### Requirement: 主审计文件中的会计样本输出必须受控
系统 MUST 在主审计文件中只保留有限会计失败样本与摘要计数，SHALL NOT 在 `audit.json` 中内联全量日级快照或全量持仓镜像。

#### Scenario: bounded sample 输出
- **WHEN** 某次实验存在多日会计失败样本
- **THEN** `audit.json` SHALL 仅保留受控数量的代表性样本
- **THEN** 审计摘要 SHALL 继续暴露总失败计数，避免样本截断改变总体判断

### Requirement: 主审计文件中的会计样本输出必须受控
系统 MUST 在主审计文件中只保留有限会计失败样本与摘要计数，SHALL NOT 在 `audit.json` 中内联全量日级快照或全量持仓镜像。

#### Scenario: bounded sample 输出
- **WHEN** 某次实验存在多日会计失败样本
- **THEN** `audit.json` SHALL 仅保留受控数量的代表性样本
- **THEN** 审计摘要 SHALL 继续暴露总失败计数，避免样本截断改变总体判断

