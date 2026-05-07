# architecture-doc Specification

## Purpose

定义系统架构文档的正式锚点、同步要求和引用边界，确保维护者能够从当前主文档获得与仓库现实一致的模块职责和运行链说明。

## Requirements

### Requirement: 全系统架构设计文档必须锚定正式模块职责与正式边界

系统 MUST 在 `docs/02_系统架构设计/全系统架构设计.md` 中维护当前正式模块职责、正式边界和正式实现状态，并 SHALL 将该文档作为编码实现的总架构锚点。

#### Scenario: 阅读全系统架构设计文档

- **WHEN** 维护者或 AI 阅读 `docs/02_系统架构设计/全系统架构设计.md`
- **THEN** 文档 MUST 明确列出实验装配层、Web 表现层、移动端入口层、API 与配置编译层、数据与特征底座、市场状态引擎、组合总控、A 股个股子系统、ETF 子系统、执行内核、正式记账与正式审计、研究诊断层、组合研究拼接层的职责

#### Scenario: 文档区分正式层与研究层

- **WHEN** 文档描述研究诊断层、研究拼接层或其他研究入口
- **THEN** 文档 MUST 明确这些层属于研究解释或研究对照层
- **THEN** 文档 SHALL NOT 将其写成正式运行真相层

### Requirement: 架构文档必须与当前仓库现实同步

系统 MUST 维护与当前仓库现实一致的架构文档，至少覆盖当前目录结构、正式模块职责、正式边界、主路径/过渡路径/产物路径边界、正式入口和主要运行链。

#### Scenario: 阅读当前架构文档

- **WHEN** 维护者或 AI 阅读当前架构文档
- **THEN** 文档 MUST 能反映 `backend/api`、`backend/core`、`backend/research`、`frontend`、`research`、`tests` 和 `openspec` 的当前职责
- **THEN** 文档 MUST 明确指出 `backend/scripts` 与旧前端壳文件属于过渡层而非长期主路径
- **THEN** 文档 MUST 明确区分正式模块、研究模块和兼容模块

#### Scenario: 正式边界发生调整

- **WHEN** 组合总控、子系统、执行内核、正式审计或研究诊断层的正式职责发生调整
- **THEN** `docs/02_系统架构设计/全系统架构设计.md` MUST 同步更新
- **THEN** 文档 SHALL NOT 长期保留与仓库现实冲突的边界描述

### Requirement: 系统架构文档必须把候选边界层写成正式共享主链的一部分

系统架构文档 MUST 明确写出“子系统 -> 候选边界层 -> 执行内核 -> 正式审计”的正式共享主链，并说明候选边界层负责子系统名额、兼容裁决和最终候选集合确认。文档 SHALL NOT 再把这些职责归到 `order_planning`。

#### Scenario: 阅读全系统架构设计文档中的共享执行链

- **WHEN** 维护者阅读正式系统架构设计文档
- **THEN** 文档 MUST 明确候选边界层位于子系统与执行内核之间
- **THEN** 文档 MUST 说明 `order_planning` 只负责订单规划和执行级 sizing

### Requirement: 系统架构文档必须显式包含候选规划层

系统架构文档 MUST 在当前正式运行链中显式表达候选规划层位于 `candidate_boundary_v1` 与执行内核之间，并说明其负责候选排序收敛、现金感知选择和轮换替换等兼容规划语义。

#### Scenario: 阅读执行链路图

- **WHEN** 维护者阅读正式系统架构设计文档
- **THEN** 文档 MUST 能明确看到候选规划层的正式位置
- **THEN** 文档 SHALL NOT 继续把这些兼容规划语义描述为执行内核内部职责

### Requirement: 架构文档必须把 order_planning 锚定为纯执行内核

系统架构文档 MUST 明确 `order_planning` 属于共享执行内核，而不是候选规划兼容层。文档 MUST 表述为：候选边界和候选规划在进入 `order_planning` 之前已经完成，`order_planning` 只负责执行级转换。

#### Scenario: 维护者阅读执行链路

- **WHEN** 维护者阅读全系统架构设计中的执行链路说明
- **THEN** 文档 MUST 明确列出 `candidate_boundary_v1 -> candidate_plan_v1 -> order_planning -> target_book_v1`
- **THEN** 文档 SHALL NOT 把 `order_planning` 描述为继续解释候选规划参数的兼容层

### Requirement: 架构文档必须把 sizing 真相描述为单一路径

系统架构文档 MUST 明确描述正式执行链的 sizing 真相只存在于共享执行路径中，而不是分散在候选规划、执行订单和兼容入口三处。

#### Scenario: 维护者阅读执行链文档

- **WHEN** 维护者阅读全系统架构设计中的执行链说明
- **THEN** 文档 MUST 将 `build_rebalance_orders()` 描述为兼容编排层
- **THEN** 文档 MUST 明确正式 sizing 真相由共享执行路径提供

### Requirement: 架构文档必须明确区分 ETF 正式合同与研究诊断

系统架构文档 MUST 明确把 ETF 子系统分成两条语义路径：一条是进入共享执行链和正式审计的正式合同路径，另一条是只服务研究解释与排障的研究诊断路径。文档 SHALL NOT 再把 ETF 中间预算、节奏、缺口字段描述为共享正式真相。

#### Scenario: 阅读 ETF 正式路径

- **WHEN** 维护者阅读系统架构文档中的 ETF 子系统章节
- **THEN** 文档 MUST 明确指出 ETF 正式路径只服务于最终目标持仓、正式审计和正式归因
- **THEN** 文档 SHALL NOT 把研究诊断字段描述为执行内核或正式审计必须消费的字段

#### Scenario: 阅读 ETF 研究路径

- **WHEN** 维护者阅读系统架构文档中的研究诊断章节
- **THEN** 文档 MUST 明确指出 ETF 中间预算、节奏、缺口和恢复解释属于研究诊断路径
- **THEN** 文档 MUST 说明这些字段不得继续定义共享正式合同

### Requirement: 守则引用的协议文档与示例必须实际存在

系统 MUST 让架构守则引用的协议文档和示例目录在仓库中实际存在，并与当前正式产物协议保持一致。

#### Scenario: 检查守则引用

- **WHEN** 守则或架构文档引用 schema 文档、example 目录或 runbook
- **THEN** 这些文件和目录 MUST 在仓库中实际存在
- **THEN** 其内容 MUST 与当前正式产物协议和主线运行方式一致

#### Scenario: 正式产物协议发生调整

- **WHEN** `run_meta`、`manifest`、`rows` 或示例产物协议发生正式调整
- **THEN** 对应 schema 文档和 example 目录 MUST 同步更新
- **THEN** 守则文本 SHALL NOT 再引用缺失或过时的路径
