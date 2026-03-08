## ADDED Requirements

### Requirement: 内部产物消费者必须通过 manifest 或 internal helper 读取产物
内部脚本、诊断工具与迁移 helper 读取实验产物时 MUST 通过 manifest 声明的相对路径，或通过显式 internal helper 获取等价映射。  
系统 SHALL NOT 继续把原始文件名、裸目录布局或散落的路径猜测当成主消费协议。

#### Scenario: 内部脚本读取核心产物
- **WHEN** 某个内部脚本需要读取 `perf`、`nav`、`run_meta`、`config` 等核心产物
- **THEN** 它 MUST 基于 manifest 声明路径或 internal helper 提供的等价路径解析结果工作

#### Scenario: 内部脚本读取可选导出物
- **WHEN** 某个内部脚本需要读取 `report.html` 这类可选导出物
- **THEN** 它 MAY 通过 manifest 或 internal helper 读取该可选产物，但其缺失 SHALL NOT 被视为核心产物发现失败
