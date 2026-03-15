## ADDED Requirements

### Requirement: 高频研究脚本必须优先迁入 study 和 CLI 主路径
系统 MUST 优先将高频研究脚本迁入 `study definition + CLI + generated thin script` 主路径。顶层 `backend/scripts/*.py` 中被标记为主线研究或高频正式命令的脚本 SHALL NOT 长期保留重型实现。

#### Scenario: 迁移高频研究脚本
- **WHEN** 某个高频研究脚本仍在顶层 `backend/scripts/*.py` 中承载主要实验逻辑
- **THEN** 系统 MUST 将其迁入 `.study.yaml` 和 `backend/cli/*`
- **THEN** 顶层脚本若继续保留，MUST 退化为薄 wrapper 或 archive

#### Scenario: 新增主线研究入口
- **WHEN** 需要新增主线研究入口
- **THEN** 系统 MUST 先定义 study 或 CLI 命令
- **THEN** SHALL NOT 新建新的顶层大型研究脚本

### Requirement: 顶层活跃脚本面必须持续收缩并可审计
系统 MUST 对顶层脚本面设置持续收缩目标，并通过 inventory 与 governance 测试阻止活跃脚本数量反弹。脚本分类结果 MUST 可审计。

#### Scenario: 清理一批顶层脚本
- **WHEN** 某批顶层脚本完成迁移或归档
- **THEN** `backend/scripts/inventory.json` MUST 更新其分类与宿主路径
- **THEN** governance 测试 MUST 能发现新的顶层活跃脚本回流

#### Scenario: generated thin script 按需生成
- **WHEN** 某个 study 需要保留脚本入口
- **THEN** 系统 MAY 生成 `backend/scripts/generated/run_<study_id>.py`
- **THEN** 该脚本 MUST 只承担参数透传和入口委托，不得承载研究主逻辑
