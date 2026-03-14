## ADDED Requirements

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
