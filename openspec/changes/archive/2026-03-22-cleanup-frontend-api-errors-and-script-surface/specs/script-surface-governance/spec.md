## ADDED Requirements

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
