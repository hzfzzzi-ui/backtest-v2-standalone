# backtest-research-audit Specification

## Purpose
为每次回测实验提供统一的 research audit 结论，用于判断实验结果是否可信，并在 governed multi-sleeve 主线下把状态、预算、sleeve 和人工 override 的证据统一串成可追溯结论。
## Requirements
### Requirement: 实验必须生成统一的 research audit 结论
系统 MUST 在每次实验的 `audit.json` 中生成 `research_audit` 子树，用于表达该实验结果是否可信。

#### Scenario: research audit 正常生成
- **WHEN** 一次实验完成并进入标准 artifact stabilize 阶段
- **THEN** `audit.json` SHALL 包含 `research_audit.contract_version`
- **THEN** `audit.json` SHALL 包含 `research_audit.overall_status`
- **THEN** `audit.json` SHALL 包含 `research_audit.gates`
- **THEN** `audit.json` SHALL 包含 `research_audit.evidence_refs`

#### Scenario: 不新增第二份元数据文件
- **WHEN** 系统生成 research audit
- **THEN** 系统 SHALL 将 research verdict 写入现有 `audit.json`
- **THEN** 系统 SHALL NOT 生成额外的 `research_audit.json`

---

### Requirement: overall_status 必须按统一聚合规则生成
系统 MUST 按 gate 状态统一聚合 `overall_status`，且聚合规则在所有实验中保持一致。

#### Scenario: 任一 gate 失败
- **WHEN** 任一 gate 的状态为 `FAIL`
- **THEN** `research_audit.overall_status` SHALL 为 `FAIL`

#### Scenario: 无失败但存在告警
- **WHEN** 所有 gate 都不是 `FAIL`，且至少一个 gate 为 `WARN`
- **THEN** `research_audit.overall_status` SHALL 为 `WARN`

#### Scenario: 无失败无告警但存在未知
- **WHEN** 所有 gate 都不是 `FAIL` 或 `WARN`，且至少一个 gate 为 `UNKNOWN`
- **THEN** `research_audit.overall_status` SHALL 为 `UNKNOWN`

#### Scenario: 全部通过
- **WHEN** 所有 gate 的状态均为 `PASS`
- **THEN** `research_audit.overall_status` SHALL 为 `PASS`

---

### Requirement: timing_alignment gate 必须保守判断时间对齐风险
系统 MUST 对时间错位和未来信息风险给出保守判定；无法证明安全时不得轻易给出 `PASS`。

#### Scenario: 明确发现同日信号同日成交
- **WHEN** 审计证据显示同日收盘信号被同日收盘成交
- **THEN** `timing_alignment.status` SHALL 为 `FAIL`

#### Scenario: 明确发现未来输入
- **WHEN** 审计证据显示信号使用了未来财务数据、未来成分股或其他未来可见信息
- **THEN** `timing_alignment.status` SHALL 为 `FAIL`

#### Scenario: 只能证明 next-day execution
- **WHEN** 系统只能证明 execution shell 遵守 next-trading-day contract，但无法证明信号输入 PIT-safe
- **THEN** `timing_alignment.status` SHALL 为 `UNKNOWN`

#### Scenario: 执行壳元信息冲突
- **WHEN** execution shell、stage metadata 或执行摘要之间存在不一致
- **THEN** `timing_alignment.status` SHALL 为 `WARN`

---

### Requirement: universe_lineage gate 必须统一到四种标准模式
系统 MUST 将实验股票池来源统一映射为 `PIT_DYNAMIC`、`START_SNAPSHOT`、`CURRENT_SNAPSHOT`、`UNKNOWN` 之一，并据此给出状态。

#### Scenario: point-in-time 动态股票池
- **WHEN** 股票池按历史时点动态变化，且系统能证明成员会按生效日或逐日 as-of 切换
- **THEN** `universe_lineage.lineage_mode` SHALL 为 `PIT_DYNAMIC`
- **THEN** `universe_lineage.status` SHALL 为 `PASS`

#### Scenario: 起始日快照股票池
- **WHEN** 股票池只在 `start_date` 解析一次并在整个回测区间固定使用
- **THEN** `universe_lineage.lineage_mode` SHALL 为 `START_SNAPSHOT`
- **THEN** `universe_lineage.status` SHALL 为 `WARN`

#### Scenario: 当前或结束时点快照回看历史
- **WHEN** 股票池在当前时点或实验结束时点解析一次，再回跑整个历史区间
- **THEN** `universe_lineage.lineage_mode` SHALL 为 `CURRENT_SNAPSHOT`
- **THEN** `universe_lineage.status` SHALL 为 `FAIL`

#### Scenario: 股票池来源无法判断
- **WHEN** 现有元信息不足以区分动态股票池、起始快照或当前快照
- **THEN** `universe_lineage.lineage_mode` SHALL 为 `UNKNOWN`
- **THEN** `universe_lineage.status` SHALL 为 `UNKNOWN`

---

### Requirement: execution_realism gate 必须检查成交是否违反基本市场约束
系统 MUST 在实验级别检查成交是否存在停牌成交、缺 bar 成交、零成交量成交、零成交额成交、涨停买入或跌停卖出等现实性风险。

#### Scenario: 明确出现不可成交填单
- **WHEN** 任一成交被判定为停牌成交、缺 bar 成交、零成交量成交或零成交额成交
- **THEN** `execution_realism.status` SHALL 为 `FAIL`

#### Scenario: 少量涨停买入或跌停卖出
- **WHEN** 涨停买入或跌停卖出占总成交笔数大于 0 且不高于 1%
- **THEN** `execution_realism.status` SHALL 为 `WARN`

#### Scenario: 大量涨停买入或跌停卖出
- **WHEN** 涨停买入或跌停卖出占总成交笔数高于 1%
- **THEN** `execution_realism.status` SHALL 为 `FAIL`

#### Scenario: 无交易或无法核对
- **WHEN** 实验没有交易记录，或系统无法回查成交对应的 bar 证据
- **THEN** `execution_realism.status` SHALL 为 `UNKNOWN`

---

### Requirement: reproducibility gate 必须判断实验是否可复现
系统 MUST 基于核心产物、配置快照与配置 hash 判断实验是否具备最小可复现性。

#### Scenario: 核心产物齐全且可追溯
- **WHEN** `run_meta.json`、`manifest.json`、`audit.json` 存在，且配置快照或配置 hash 能追溯本次运行
- **THEN** `reproducibility.status` SHALL 为 `PASS`

#### Scenario: 核心产物存在但配置追溯不完整
- **WHEN** 核心产物存在，但配置快照不完整且只能通过部分 hash 或元信息回溯
- **THEN** `reproducibility.status` SHALL 为 `WARN`

#### Scenario: 关键产物缺失
- **WHEN** `run_meta.json`、`manifest.json` 或 `audit.json` 缺失
- **THEN** `reproducibility.status` SHALL 为 `FAIL`

#### Scenario: 证据无法读取
- **WHEN** manifest 或关键 artifact 无法读取，导致系统无法完成可复现性判断
- **THEN** `reproducibility.status` SHALL 为 `UNKNOWN`

---

### Requirement: result_sanity gate 必须检测明显异常结果
系统 MUST 对异常收益、异常风险和明显自相矛盾的结果给出风险标记，但不得把该 gate 用作策略优劣评分。

#### Scenario: 极端异常且样本充分
- **WHEN** 样本满足最小门槛，且 Sharpe 超过 5 或 CAGR 超过 100%
- **THEN** `result_sanity.status` SHALL 为 `FAIL`

#### Scenario: 指标偏极端
- **WHEN** 样本满足最小门槛，且 Sharpe 超过 3 或 CAGR 超过 50%，或利润明显过度集中
- **THEN** `result_sanity.status` SHALL 为 `WARN`

#### Scenario: 指标口径自相矛盾
- **WHEN** 审计证据显示交易数、净值、收益或计数器之间存在明显矛盾
- **THEN** `result_sanity.status` SHALL 为 `FAIL`

#### Scenario: 指标不足
- **WHEN** 关键收益或交易指标缺失，或样本不足以进行异常检测
- **THEN** `result_sanity.status` SHALL 为 `UNKNOWN`

---

### Requirement: research audit 必须引用证据而不是复制既有产物
系统 MUST 在 `research_audit` 中引用已有 artifact 作为证据源，而不是复制完整 payload。

#### Scenario: 引用现有实验产物
- **WHEN** `research_audit` 生成完成
- **THEN** `research_audit.evidence_refs` SHALL 至少包含 `run_meta`、`manifest`、`stage_summary`
- **THEN** `research_audit.evidence_refs` SHALL 使用 artifact 路径或等价引用，而不是内嵌完整文件内容

#### Scenario: validate_data 为可选证据
- **WHEN** 本次实验没有可追溯的 `validate_data` 结果
- **THEN** `research_audit.evidence_refs.validate_data` SHALL 为 `null`
- **THEN** 系统 SHALL NOT 因缺少 `validate_data` 引用而拒绝生成 `research_audit`

### Requirement: timing_alignment 必须优先消费显式 lineage 证据
系统 MUST 在实验提供 execution lineage 证据时，优先依据 `signal_date`、`scheduled_date`、`fill_date` 和终态记录判断时间对齐风险，而不是仅依赖配置推断。

系统 MUST 在实验提供 execution lineage 证据时，优先依据 `signal_date`、`scheduled_date`、`fill_date` 和终态记录判断时间对齐风险，而不是仅依赖配置推断。

#### Scenario: 明确发现同日生成同日成交
- **WHEN** lineage 证据显示某条以收盘后信号为前提的交易在同一交易日完成成交
- **THEN** `research_audit.gates.timing_alignment.status` SHALL 为 `FAIL`

#### Scenario: 明确证明 next-day contract 成立
- **WHEN** lineage 证据显示信号在 T 日生成、订单在 T+1 排程并以符合合同的方式终结，且其他 PIT-safe 条件成立
- **THEN** `research_audit.gates.timing_alignment` SHALL 可以基于显式 lineage 证据给出 `PASS`

#### Scenario: lineage 证据缺失或不完整
- **WHEN** 当前实验没有 lineage 证据，或证据不足以证明完整链路
- **THEN** `timing_alignment` SHALL 回退到既有推断路径或输出 `UNKNOWN`
- **THEN** 系统 SHALL NOT 因缺少显式 lineage 证据而伪造 `PASS`### Requirement: research_audit 必须包含 accounting_integrity gate
系统 MUST 在 `research_audit.gates` 中新增 `accounting_integrity` gate，并基于主线 execution audit 的会计恒等式证据输出统一状态。

系统 MUST 在 `research_audit.gates` 中新增 `accounting_integrity` gate，并基于主线 execution audit 的会计恒等式证据输出统一状态。

#### Scenario: 会计恒等式出现失败
- **WHEN** execution audit 证据显示现金守恒、持仓守恒、NAV 一致性、负现金或超仓上限中任一硬性检查失败
- **THEN** `research_audit.gates.accounting_integrity.status` SHALL 为 `FAIL`

#### Scenario: 证据完整且全部通过
- **WHEN** execution audit 提供了完整的主线会计证据，且所有硬性检查均通过
- **THEN** `research_audit.gates.accounting_integrity.status` SHALL 为 `PASS`

#### Scenario: 主线证据不足
- **WHEN** 当前实验缺少足够的主线会计快照，导致系统无法证明记账自洽
- **THEN** `research_audit.gates.accounting_integrity.status` SHALL 为 `UNKNOWN`
- **THEN** 该 gate SHALL 通过 `reason` 或等价字段说明证据不足，而不是默认为 `PASS`

### Requirement: research audit 必须引用A股统一归因证据链
当实验属于 A 股 governed multi-sleeve 主线时，`backtest-research-audit` MUST 引用 `market_regime_engine`、`global_portfolio_governor`、各 sleeve 和 `manual_override` 的统一 attribution 证据，而 SHALL NOT 只引用孤立的收益或执行产物。

#### Scenario: A股 governed 实验引用 attribution 证据
- **WHEN** 实验运行属于 A 股 governed multi-sleeve 口径
- **THEN** `research_audit.evidence_refs` MUST 引用 regime、budget、sleeve 和 override 相关证据

### Requirement: research audit 必须能回答仓位与状态来源
当实验属于 A 股 governed multi-sleeve 主线时，research audit MUST 允许回答以下问题：
- 今天的生效状态来自哪里
- 今天的预算变化来自哪里
- 某个 sleeve 为什么被压缩或停用
- 是否存在人工 override

#### Scenario: 审计结论可解释仓位变化
- **WHEN** 用户查看 governed 主线实验的 research audit
- **THEN** audit MUST 能定位到相应的状态、预算和 sleeve 证据
- **THEN** audit SHALL NOT 只给出最终 PASS/WARN/FAIL 而没有可追溯来源

