## ADDED Requirements

### Requirement: 正式实验入口必须默认收口到 study 与 generated thin script
系统 MUST 将正式实验入口默认收口到 `.study.yaml`、`backend.cli study_run` 与 `backend/scripts/generated/run_<study_id>.py`。新的主线实验 SHALL NOT 再以顶层大型研究脚本作为默认入口。

#### Scenario: 新增主线实验
- **WHEN** 需要新增一个主线实验入口
- **THEN** 系统 MUST 先创建 study 定义或复用既有 study runner
- **THEN** 系统 MAY 按需生成 thin script
- **THEN** 系统 SHALL NOT 再新增顶层大型研究脚本

#### Scenario: AI 直接发起实验
- **WHEN** AI 需要为某个主线实验生成可直接执行的入口
- **THEN** 系统 MUST 优先生成或复用 generated thin script
- **THEN** 系统 SHALL NOT 默认回退到手写顶层 `run_*_research.py`

### Requirement: 高频主线研究脚本必须持续迁入 study 主路径
系统 MUST 持续将高频主线研究脚本迁入 study 主路径，并通过 inventory 与 governance 测试约束顶层脚本面收缩。

#### Scenario: 迁移一批高频研究脚本
- **WHEN** 某批高频研究脚本完成 study 化迁移
- **THEN** `backend/scripts/inventory.json` MUST 更新分类、宿主路径和 generated thin script 映射
- **THEN** 顶层脚本若继续保留，MUST 退化为 archive 或极薄 wrapper
