# artifact-finalization-pipeline Specification

## Purpose
定义实验产物稳定化与 finalize pipeline 的模块边界，确保 `artifacts_impl.py` 只保留 facade 入口，具体 artifact finalize 逻辑按职责拆分，同时保持标准 artifact 协议稳定。
## Requirements
### Requirement: Artifact finalize MUST 按产物职责分层
系统 MUST 将实验产物稳定化和 finalize 流程按职责拆分为独立模块。`artifacts_impl.py` SHALL 只保留 facade 入口，具体逻辑 MUST 至少拆分为 `io`、`manifest`、`stage-summary`、`diagnostics` 和 `finalize` 模块。

#### Scenario: 实验结果写入 manifest
- **WHEN** 系统为实验目录生成或更新 `manifest.json`
- **THEN** facade MUST 调度 manifest 模块完成相关逻辑
- **THEN** manifest 逻辑 SHALL NOT 与 CSV/JSON I/O 或 diagnostics 长期混写在同一实现块中

#### Scenario: 生成阶段漏斗和 counters
- **WHEN** 系统构建 buy funnel、stage summary 或 counters
- **THEN** 相关逻辑 MUST 进入独立 stage-summary 模块
- **THEN** facade SHALL 只负责装配和暴露统一入口

### Requirement: Artifact diagnostics MUST 独立于 finalize facade
系统 MUST 将 `symbol performance`、`reason codes`、`stock names`、`ST flag` 等 diagnostics 逻辑与 facade 分离。diagnostics 模块 SHALL 成为新增诊断产物的唯一扩展点。

#### Scenario: 新增诊断类产物
- **WHEN** 后续需要新增 symbol 或 reason diagnostics
- **THEN** 系统 MUST 在 diagnostics 模块扩展
- **THEN** 系统 SHALL NOT 再把新诊断直接堆回 facade 文件

### Requirement: 模块化不得改变标准 artifact 协议
系统 MUST 保持现有标准产物协议不变，包括 `manifest.json`、`perf.json`、`nav.csv`、`run_meta.json` 及相关 `surface` 引用。模块化 SHALL NOT 通过重命名或改变路径语义破坏现有主路径。

#### Scenario: 稳定化 baseline 目录
- **WHEN** 系统对 `baseline_V10.1` 对应实验目录执行 artifact stabilize
- **THEN** 产物文件名、surface 引用和 canonical schema MUST 与拆分前保持兼容
- **THEN** 模块化 SHALL NOT 影响桌面结果工作台或查询服务的读取语义

### Requirement: Artifact diagnostics MUST 输出最近一周资金不足拦截买入明细
系统 MUST 在实验 finalize pipeline 中生成 `cash_blocked_buys_recent.csv`，用于记录最近 5 个交易日内因资金不足被拦截的买入候选明细。该 artifact SHALL 只包含明确的 `SKIP_NO_CASH` 事件，而 SHALL NOT 混入一般性未入选候选。

#### Scenario: 最近一周存在资金不足拦截
- **WHEN** 候选审计中存在 `SKIP_NO_CASH` 事件
- **THEN** 系统 MUST 输出 `cash_blocked_buys_recent.csv`
- **THEN** 该文件 MUST 至少包含 `date`、`symbol`、`cash_available`、`estimated_qty`、`estimated_amount`
- **THEN** 该文件 MUST 只保留最近 5 个交易日范围内的记录

#### Scenario: 最近一周没有资金不足拦截
- **WHEN** 候选审计中不存在最近 5 个交易日的 `SKIP_NO_CASH` 事件
- **THEN** 系统 MUST 仍输出 `cash_blocked_buys_recent.csv`
- **THEN** 该文件 SHALL 为空表，但表头 MUST 稳定存在

#### Scenario: cash-aware 未选中但不属于明确现金不足
- **WHEN** 候选仅因 `NOT_SELECTED_CASH_AWARE` 等原因未入选
- **THEN** 系统 SHALL NOT 将这些候选写入 `cash_blocked_buys_recent.csv`

### Requirement: Artifact diagnostics 必须只消费 canonical runtime diagnostics input
系统 MUST 要求 `artifacts_diagnostics.py` 及相关 diagnostics/funnel builder 只消费 canonical runtime diagnostics input，不再直接从执行本体推导最终 stage 语义。

系统 MUST 要求 `artifacts_diagnostics.py` 及相关 diagnostics/funnel builder 只消费 canonical runtime diagnostics input，不再直接从执行本体推导最终 stage 语义。

#### Scenario: 生成 buy stage funnel
- **WHEN** 系统为实验结果生成 buy stage funnel
- **THEN** diagnostics builder MUST 通过 canonical diagnostics input 构建阶段计数和 note
- **THEN** diagnostics builder SHALL NOT 直接绑定执行层私有局部状态

#### Scenario: 生成 counters 与 reason diagnostics
- **WHEN** 系统生成 counters、reason summaries 或 surface diagnostics
- **THEN** 系统 MUST 复用同一份 canonical diagnostics input
- **THEN** 不同 artifact SHALL NOT 各自重复定义 stage count 归一化规则
