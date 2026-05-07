## REMOVED Requirements

### Requirement: ARCHITECTURE.md 架构文档
**Reason**: 根目录文档已收敛到 `docs/` 体系，系统总架构真相不再由根目录 `ARCHITECTURE.md` 承载。  
**Migration**: 使用 `docs/02_系统架构设计/全系统架构设计.md` 作为当前系统总架构文档。

## ADDED Requirements

### Requirement: 全系统架构设计文档必须锚定正式模块职责与正式边界
系统 MUST 在 `docs/02_系统架构设计/全系统架构设计.md` 中维护当前正式模块职责、正式边界和正式实现状态，并 SHALL 将该文档作为编码实现的总架构锚点。

#### Scenario: 阅读全系统架构设计文档
- **WHEN** 维护者或 AI 阅读 `docs/02_系统架构设计/全系统架构设计.md`
- **THEN** 文档 MUST 明确列出实验装配层、Web 表现层、移动端入口层、API 与配置编译层、数据与特征底座、市场状态引擎、组合总控、A 股个股子系统、ETF 子系统、执行内核、正式记账与正式审计、研究诊断层、组合研究拼接层的职责

#### Scenario: 文档区分正式层与研究层
- **WHEN** 文档描述研究诊断层、研究拼接层或其他研究入口
- **THEN** 文档 MUST 明确这些层属于研究解释或研究对照层
- **THEN** 文档 SHALL NOT 将其写成正式运行真相层

## MODIFIED Requirements

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
