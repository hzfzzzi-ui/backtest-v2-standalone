## ADDED Requirements

### Requirement: 实验产物稳定化必须通过核心 artifact service

系统 MUST 提供核心 artifact service，承接实验产物稳定化、manifest 写入、标准产物补齐和共享读取边界。脚本层与 API 层 SHALL 通过该 service 完成产物稳定化，而不是直接复用 endpoint 辅助函数。

#### Scenario: API 写入标准产物
- **WHEN** 实验运行成功并需要补齐标准产物
- **THEN** API 层 SHALL 调用核心 artifact service
- **THEN** endpoint 文件 SHALL NOT 成为唯一 artifact owner

#### Scenario: 脚本使用产物稳定化
- **WHEN** baseline gate、consistency check 或内部 helper 需要稳定化实验目录
- **THEN** 脚本 SHALL 调用核心 artifact service
- **THEN** 脚本 SHALL NOT 直接 import `backtest_v2_artifacts` 中的稳定化函数

### Requirement: artifact service 不得改变现有 artifact 契约

artifact service 下沉 MUST 保持 `manifest.json`、`perf.json`、`nav.csv`、`run_meta.json`、`audit.json` 等现有 artifact 协议不变。

#### Scenario: 前端读取实验产物
- **WHEN** 前端通过 `experiment_id + manifest` 读取实验产物
- **THEN** 文件名和读取路径 SHALL 保持兼容
- **THEN** 前端无需因 service 下沉修改 artifact 消费逻辑
