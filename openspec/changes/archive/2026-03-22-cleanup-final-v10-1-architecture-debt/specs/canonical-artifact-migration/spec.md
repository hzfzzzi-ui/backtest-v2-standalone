## MODIFIED Requirements

### Requirement: 运行时读取链必须只认 canonical artifact schema
系统 MUST 以 canonical artifact 命名和 canonical counter 字段作为运行时唯一真相。查询服务、API 返回和前端主路径 SHALL NOT 继续在运行时常驻历史 alias、legacy trades 文件名或旧 shell label 归一化逻辑。

#### Scenario: 查询实验 artifact
- **WHEN** 查询服务读取某个实验目录的标准 artifact
- **THEN** 读取链 MUST 直接消费 canonical 文件名和 canonical counters
- **THEN** 运行时 SHALL NOT 再依赖历史 alias 作为长期主路径

#### Scenario: 新实验写出产物
- **WHEN** 新实验写出 `manifest.json`、`perf.json`、`run_meta.json` 等标准产物
- **THEN** 系统 MUST 只写出 canonical 命名
- **THEN** 新实验 SHALL NOT 再生成旧 alias

### Requirement: 历史产物兼容必须退出运行时并改为离线迁移
系统 MUST 将历史 artifact alias、旧 counter 字段和旧 shell label 的处理限制在离线迁移工具与迁移审计中。运行时 contract SHALL NOT 再为这些历史名称保留常驻兼容读取。

#### Scenario: 需要读取旧产物目录
- **WHEN** 某批历史产物仍使用旧命名
- **THEN** 系统 MUST 先通过离线 migration 将其转成 canonical schema
- **THEN** 运行时接口 SHALL NOT 因这些旧产物继续保留兼容分支

#### Scenario: 迁移后回归校验
- **WHEN** 历史产物完成 canonical migration
- **THEN** 系统 MUST 以前后对照 `baseline_V10.1 -> exp_20260314_144548534_7db9` 复核读取结果
- **THEN** 若出现结果漂移，迁移 SHALL NOT 进入主路径

