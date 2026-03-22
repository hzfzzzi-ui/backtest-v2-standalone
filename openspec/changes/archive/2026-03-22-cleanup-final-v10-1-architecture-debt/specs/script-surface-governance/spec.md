## MODIFIED Requirements

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

### Requirement: 顶层研究定义脚本必须持续迁出
系统 MUST 持续将被标记为 `study-definition` 的顶层研究脚本迁入 `research/studies/*.study.yaml + backend.cli study_run + generated thin script`。已过时研究若无保留价值 MUST 直接删除。

#### Scenario: 迁移一批研究脚本
- **WHEN** 某批研究脚本完成 study 化迁移
- **THEN** `backend/scripts/inventory.json` MUST 更新分类、映射和删除状态
- **THEN** governance 测试 MUST 能阻止这批顶层入口重新回流

#### Scenario: 研究已经过时
- **WHEN** 某个研究脚本对应的实验方向已经过时或无保留价值
- **THEN** 系统 MUST 允许直接删除该入口
- **THEN** 系统 SHALL NOT 为其保留前向兼容壳

