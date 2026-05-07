# script-surface-governance Specification

## Purpose

定义正式脚本面、study 入口、脚本分类治理和 baseline 台账更新要求，确保脚本入口可审计、可收敛、可维护。

## Requirements

### Requirement: 活跃脚本面必须被限制为正式命令面与 generated thin script

系统 MUST 将活跃研究脚本面限制为 `backend/cli/main.py`、`research/studies/*.study.yaml` 与 `backend/scripts/generated/run_<study_id>.py`。顶层 `backend/scripts/run_*_research.py` SHALL NOT 再作为正式研究入口保留。

#### Scenario: 新增正式研究入口

- **WHEN** 需要新增正式研究入口
- **THEN** 系统 MUST 先定义 study 或 CLI 命令
- **THEN** 系统 MAY 按需生成 thin script
- **THEN** 系统 SHALL NOT 再新增顶层大型研究脚本

#### Scenario: 已过时顶层研究脚本

- **WHEN** 顶层 `run_*_research.py` 已存在等价 study 路线，且不再承担正式主线研究职责
- **THEN** 该脚本 MUST 被删除
- **THEN** 不得再保留仅为历史习惯服务的 wrapper

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

### Requirement: 高频研究脚本必须优先迁入 study 与 CLI 主路径

系统 MUST 优先将高频研究脚本迁入 `study definition + CLI + generated thin script` 主路径。顶层 `backend/scripts/*.py` 中被标记为主线研究或高频正式命令的脚本 SHALL NOT 长期保留重型实现。

#### Scenario: 迁移高频研究脚本

- **WHEN** 某个高频研究脚本仍在顶层 `backend/scripts/*.py` 中承载主要实验逻辑
- **THEN** 系统 MUST 将其迁入 `.study.yaml` 和 `backend/cli/*`
- **THEN** 顶层脚本若继续保留，MUST 退化为薄 wrapper 或 archive

#### Scenario: 新增主线研究入口

- **WHEN** 需要新增主线研究入口
- **THEN** 系统 MUST 先定义 study 或 CLI 命令
- **THEN** SHALL NOT 新建新的顶层大型研究脚本

### Requirement: 已迁移顶层脚本必须保持薄 wrapper 形态

系统 MUST 要求已迁移的顶层脚本保持薄 wrapper 形态。对于已迁移到 CLI 或 study runner 的脚本，顶层 `backend/scripts/*.py` SHALL 只保留最小路径引导与委托调用。

#### Scenario: study 已迁移完成

- **WHEN** 某个研究专题已经迁移到 `.study.yaml` 与 `study_run`
- **THEN** 对应顶层脚本 MUST 只保留薄 wrapper
- **THEN** 顶层脚本 SHALL NOT 再包含实验矩阵、配置合成或正式业务逻辑

#### Scenario: 正式命令已迁移完成

- **WHEN** 某个正式命令已经迁移到 `backend/cli/managed/*`
- **THEN** 顶层同名脚本 MUST 只保留兼容导向入口
- **THEN** 活跃逻辑 SHALL NOT 再留在顶层脚本

### Requirement: 默认测试集必须只依赖正式脚本面

系统 MUST 让默认 `pytest` 测试集只依赖正式脚本面：`backend/cli/main.py`、`backend/cli/managed/*`、`backend/scripts/generated/run_<study_id>.py` 和明确声明的薄 wrapper。默认测试 SHALL NOT 继续直接导入已退役或未声明为正式接口的顶层脚本实现。

#### Scenario: 测试覆盖脚本行为

- **WHEN** 单元测试或集成测试需要验证脚本行为
- **THEN** 测试 MUST 调用正式 CLI surface、managed module 或 generated thin script
- **THEN** 测试 SHALL NOT 直接依赖已退役的顶层脚本实现路径

#### Scenario: 顶层 wrapper 继续保留

- **WHEN** 顶层 `backend/scripts/*.py` 因兼容原因暂时保留
- **THEN** 该文件 MUST 只承担单向委托或参数透传职责
- **THEN** 默认测试 MAY 校验其委托关系
- **THEN** 默认测试 SHALL NOT 把该 wrapper 当作长期主实现宿主

### Requirement: 兼容脚本退场必须同步更新 inventory 与治理测试

系统 MUST 在每次脚本迁移、删除或降级为 wrapper 时同步更新 `backend/scripts/inventory.json` 与治理测试，保证脚本面现状可审计。

#### Scenario: 某个脚本从主实现降级为 wrapper

- **WHEN** 某个顶层脚本不再承载主实现而仅保留薄委托
- **THEN** inventory MUST 更新其分类和宿主路径
- **THEN** 治理测试 MUST 能识别该文件已不再是主实现

#### Scenario: 某个历史脚本被完全删除

- **WHEN** 某个退役脚本被移除
- **THEN** inventory 和治理测试 MUST 同步移除对其主实现身份的假设
- **THEN** 默认测试 collect SHALL NOT 因历史导入路径而失败

### Requirement: 正式 baseline 锚点重挂必须留下可审计的 baseline 台账记录

当系统重挂既有正式 baseline 锚点时，系统 MUST 追加一条可审计的 baseline 台账记录到该 baseline 的 machine/human 资产中。该记录 MUST 写入 `experiment_ledger.jsonl`、`report_index.json`、`baseline_report.md` 和 `baseline_digest.md`；当重挂结果被登记为 `PASS` 时，系统 MUST 同步刷新 `latest_champion.json`。

#### Scenario: baseline_V10.1 官方锚点重挂成功

- **WHEN** `baseline_V10.1` 被正式重挂到新的 linked experiment，且本次重挂结果登记为 `PASS`
- **THEN** 系统 MUST 向 `outputs/baselines/baseline_V10_1/machine/experiment_ledger.jsonl` 追加一条 official rebase 记录
- **THEN** 系统 MUST 在 `outputs/baselines/baseline_V10_1/machine/report_index.json` 中追加对应条目
- **THEN** 系统 MUST 在 `outputs/baselines/baseline_V10_1/human/baseline_report.md` 与 `baseline_digest.md` 中追加对应摘要
- **THEN** 系统 MUST 将 `outputs/baselines/baseline_V10_1/machine/latest_champion.json` 更新为这次 official rebase 的 PASS 结果

### Requirement: 工作区临时产物必须受控

系统 MUST 将本地临时产物、浏览器 profile、测试输出和一次性 `tmp_*` 文件纳入工作区治理。此类产物 SHALL NOT 长期污染版本控制工作区。

#### Scenario: 本地产生临时目录或文件

- **WHEN** 调试、截图、浏览器 profile 或一次性测试运行生成临时产物
- **THEN** 系统 MUST 通过 `.gitignore` 或清理规则将其排除出长期活跃面
- **THEN** 这些产物 SHALL NOT 在日常工作区中持续作为未跟踪噪音存在

#### Scenario: 需要保留人工文档或研究报告

- **WHEN** 某个本地文件属于人工报告、研究说明或可追溯资产
- **THEN** 系统 MAY 保留该文件
- **THEN** 它 MUST 与临时产物治理策略区分开
