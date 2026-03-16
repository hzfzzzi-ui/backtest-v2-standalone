## ADDED Requirements

### Requirement: Artifact finalize 必须按产物职责分层
系统 MUST 将实验产物稳定化和 finalize 流程按职责拆分为独立模块。`artifacts_impl.py` SHALL 只保留 façade 入口，具体逻辑 MUST 至少分为 `io`、`manifest`、`stage-summary`、`diagnostics` 和 `finalize` 模块。

#### Scenario: 实验结果写入 manifest
- **WHEN** 系统为实验目录生成或更新 `manifest.json`
- **THEN** façade MUST 调度 manifest 模块完成相关逻辑
- **THEN** manifest 逻辑 SHALL NOT 与 CSV/JSON I/O 或 diagnostics 汇总长期混写在同一实现块中

#### Scenario: 生成阶段漏斗和 counters
- **WHEN** 系统构建 buy funnel、stage summary 或 counters
- **THEN** 相关逻辑 MUST 进入独立 stage-summary 模块
- **THEN** façade SHALL 只负责装配和暴露统一入口

### Requirement: Artifact diagnostics 必须独立于 finalize façade
系统 MUST 将 symbol performance、reason codes、stock names、ST flag 等 diagnostics 逻辑与 façade 分离。diagnostics 模块 SHALL 成为新增诊断产物的唯一扩展点。

#### Scenario: 新增诊断类产物
- **WHEN** 后续需要新增 symbol 或 reason diagnostics
- **THEN** 系统 MUST 在 diagnostics 模块扩展
- **THEN** 系统 SHALL NOT 再把新诊断直接堆回 façade 文件

### Requirement: 模块化不得改变标准 artifact 协议
系统 MUST 保持既有标准产物协议不变，包括 `manifest.json`、`perf.json`、`nav.csv`、`run_meta.json` 及相关 surface 引用。模块化 SHALL NOT 通过重命名或改变路径语义破坏现有主路径。

#### Scenario: 稳定化 baseline 目录
- **WHEN** 系统对 `baseline_V10.1` 对应实验目录执行 artifact stabilize
- **THEN** 产物文件名、surface 引用和 canonical schema MUST 与拆分前保持兼容
- **THEN** 模块化 SHALL NOT 影响桌面结果工作台或查询服务的读取语义
