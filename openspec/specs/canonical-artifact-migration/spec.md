# canonical-artifact-migration Specification

## Purpose
TBD - created by archiving change cleanup-remaining-architecture-debt. Update Purpose after archive.
## Requirements
### Requirement: 运行时读取链必须只认 canonical artifact schema
系统 MUST 以 canonical artifact 命名、canonical counter 字段和 canonical manifest 资产上下文作为运行时唯一真相。查询服务、API 返回和前端主路径 SHALL NOT 长期依赖查询时临时补丁去推导历史资产上下文。

#### Scenario: 查询实验 artifact
- **WHEN** 查询服务读取某个实验目录的标准 artifact
- **THEN** 读取链 MUST 直接消费 canonical 文件命名、canonical counters 和 canonical manifest 字段
- **THEN** 运行时 SHALL NOT 继续把历史 alias 或临时 asset context 推导当成长期主路径

#### Scenario: 新实验写出标准产物
- **WHEN** 新实验写出 `manifest.json`、`perf.json`、`run_meta.json` 等标准产物
- **THEN** 系统 MUST 只写出 canonical 命名和 canonical 资产上下文
- **THEN** 新实验 SHALL NOT 生成新的历史 alias 或缺失资产上下文字段的 manifest

### Requirement: 历史 artifact alias 必须通过离线迁移退出运行时
系统 MUST 提供离线迁移和迁移审计，用于把历史 artifact、counter 字段、shell label 和缺失资产上下文的 `manifest.json` 批量更新为 canonical schema。迁移完成后，历史实验的磁盘 manifest MUST 自描述其 canonical 资产边界。

#### Scenario: 回填历史 manifest 资产上下文
- **WHEN** 某个历史实验的 `manifest.json` 缺少 `asset_scope`、`asset_profile_id`、`market_profile_id`、`execution_profile_id` 或 `asset_context`
- **THEN** 迁移工具 MUST 从 `config.json`、`run_config.json`、`compiled_plan.json` 等标准输入推导并回填 canonical 字段
- **THEN** 若无法可靠推导，迁移工具 MUST 记录跳过原因并输出到审计结果，而 SHALL NOT 静默写入不可信值

#### Scenario: 迁移历史产物
- **WHEN** 需要清理历史 artifact alias
- **THEN** 系统 MUST 先输出迁移审计报告，列出受影响目录、字段、文件名与回填结果
- **THEN** 系统 MUST 通过离线迁移批量更新历史产物，再删除运行时长期 alias 归一化依赖

#### Scenario: 迁移后回归校验
- **WHEN** 某批历史产物完成 canonical migration
- **THEN** 系统 MUST 以前后对照 `V10.1 -> exp_20260314_144548534_7db9` 和代表性历史实验做读取回归
- **THEN** 若结果或 manifest 语义发生漂移，迁移 SHALL NOT 进入主路径

