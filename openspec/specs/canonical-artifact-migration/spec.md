# canonical-artifact-migration Specification

## Purpose
TBD - created by archiving change cleanup-remaining-architecture-debt. Update Purpose after archive.
## Requirements
### Requirement: 运行时读取链必须只认 canonical artifact schema
系统 MUST 以 canonical artifact 命名和 canonical counter 字段作为运行时唯一真相。查询服务、API 返回和前端主路径 SHALL NOT 继续在运行时常驻历史 alias 归一化逻辑。

#### Scenario: 查询实验 artifact
- **WHEN** 查询服务读取某个实验目录的标准 artifact
- **THEN** 读取链 MUST 直接消费 canonical 文件名和 canonical counters
- **THEN** 运行时 SHALL NOT 依赖历史 `reason_code_counts.csv`、`*_count` 等 alias 作为长期主路径

#### Scenario: 新实验写出产物
- **WHEN** 新实验写出 `manifest.json`、`perf.json`、`run_meta.json` 等标准产物
- **THEN** 系统 MUST 只写出 canonical 命名
- **THEN** 新实验 SHALL NOT 生成新的历史 alias

### Requirement: 历史 artifact alias 必须通过离线迁移退出运行时
系统 MUST 提供离线迁移和迁移审计，用于把历史 artifact、counter 字段和 shell label 批量更新为 canonical schema。只有在迁移审计通过后，运行时 alias 读取逻辑才可以被删除。

#### Scenario: 迁移历史产物
- **WHEN** 需要清理历史 artifact alias
- **THEN** 系统 MUST 先输出迁移审计报告，列出受影响目录、字段和文件名
- **THEN** 系统 MUST 通过离线迁移批量更新历史产物，再删除运行时 alias 归一化

#### Scenario: 迁移后回归校验
- **WHEN** 某批历史产物完成 canonical migration
- **THEN** 系统 MUST 以前后对照 `V10.1 -> exp_20260314_144548534_7db9` 和代表性历史实验做读取回归
- **THEN** 若结果或读取语义发生漂移，迁移 SHALL NOT 进入主路径

