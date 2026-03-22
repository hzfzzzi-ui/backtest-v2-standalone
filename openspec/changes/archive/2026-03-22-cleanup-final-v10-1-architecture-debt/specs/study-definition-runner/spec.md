## MODIFIED Requirements

### Requirement: generated thin script 必须成为默认研究脚本入口
系统 MUST 将 `backend/scripts/generated/run_<study_id>.py` 作为 study 的默认脚本入口。顶层手写 `_research.py` wrapper SHALL NOT 再作为并存的正式入口保留。

#### Scenario: 用户需要脚本式入口
- **WHEN** 某个 study 需要被直接脚本执行
- **THEN** 系统 MUST 生成或复用对应的 generated thin script
- **THEN** 该入口 SHALL 通过 `backend.cli study_run` 执行统一 study runner

#### Scenario: 已迁移专题仍保留旧 wrapper
- **WHEN** 某个研究专题已经存在 `.study.yaml` 与 generated thin script
- **THEN** 顶层 `_research.py` wrapper MUST 可以被直接删除
- **THEN** 系统 SHALL NOT 再要求保留双入口

### Requirement: study runner 必须支持批量替代顶层研究定义脚本
系统 MUST 允许批量将顶层研究定义脚本中的矩阵、窗口、baseline、patch 逻辑迁入 `.study.yaml`。迁移完成后，study runner SHALL 成为该批实验的唯一正式执行器。

#### Scenario: 迁移一组 V10 研究脚本
- **WHEN** 系统迁移一组同类型 V10 研究脚本
- **THEN** 每个专题 MUST 拥有对应 `.study.yaml`
- **THEN** 每个专题 MAY 生成 thin script
- **THEN** 顶层研究脚本 SHALL NOT 再承载矩阵定义

