# script-surface-governance Specification

## Purpose
Synced from delta spec during archive. The capability contract is now part of the main spec set.
## Requirements
### Requirement: 活跃脚本面必须被限制为正式命令面与薄脚本入口
系统 MUST 将活跃脚本面限制为 `backend/cli/main.py` 和按需生成的 `backend/scripts/generated/run_<study_id>.py`。顶层 `backend/scripts/*.py` SHALL NOT 继续作为长期活跃主入口。

#### Scenario: 新增一个正式实验入口
- **WHEN** 需要新增正式实验入口
- **THEN** 系统 MUST 选择 CLI 子命令或 generated thin script
- **THEN** 系统 SHALL NOT 新建顶层大型 `run_*.py`

#### Scenario: 顶层脚本面冻结后
- **WHEN** 旧脚本面被冻结
- **THEN** 顶层 `backend/scripts/` 只应保留 `generated/`、`archive/` 和少量内部 helper
- **THEN** 新的活跃研究脚本 SHALL NOT 出现在顶层

### Requirement: 脚本必须进行分类治理
系统 MUST 对现有脚本应用分类治理，至少支持 `official-command`、`official-audit`、`study-definition`、`archived-study`、`one-off-delete` 和 `internal-helper` 六类标签。

#### Scenario: 识别可复用脚本
- **WHEN** 某个脚本会被反复执行
- **THEN** 系统 MUST 将其归类为 `official-command` 或 `official-audit`
- **THEN** 该能力 MUST 迁移到 CLI 命令面

#### Scenario: 识别一次性残留脚本
- **WHEN** 某个脚本仅对应一次性实验且无后续复用价值
- **THEN** 系统 MUST 将其归类为 `archived-study` 或 `one-off-delete`
- **THEN** `one-off-delete` SHOULD 先归档一段时间，再删除

### Requirement: baseline 资产必须记录所有正式实验
系统 MUST 为每次正式实验更新 baseline 资产。每次实验 MUST 追加 `experiment_ledger.jsonl` 和 `baseline_report.md`；只有 `PASS` 才能申请更新 `latest_champion.json`；`FAIL` 也 MUST 进入 baseline report。

#### Scenario: 实验通过
- **WHEN** 某次实验的 `verdict` 为 `PASS`
- **THEN** 系统 MUST 追加 ledger 和 baseline report
- **THEN** 系统 MAY 申请更新 `latest_champion.json`

#### Scenario: 实验失败
- **WHEN** 某次实验的 `verdict` 为 `FAIL`
- **THEN** 系统 MUST 仍然追加 ledger 和 baseline report
- **THEN** 系统 SHALL NOT 更新 `latest_champion.json`

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

