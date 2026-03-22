# experiment-artifact-service Specification

## Purpose
定义核心 experiment artifact service 的职责边界与兼容契约。
## Requirements
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

### Requirement: artifact service 的 finalize owner 必须允许分层实现
系统 MUST 允许 experiment artifact service 通过分层 finalize pipeline 承担 manifest、summary、diagnostics 和 artifact stabilize 职责。底层 owner MAY 拆分为 `io`、`manifest`、`stage-summary`、`diagnostics` 和 `finalize` 模块，但对外 artifact service 契约 MUST 保持稳定。

#### Scenario: API 触发 artifact stabilize
- **WHEN** API 或 service 触发一次实验目录稳定化
- **THEN** 底层实现 MAY 调度分层 finalize 模块完成工作
- **THEN** artifact service 对外入口和标准产物协议 MUST 保持不变

#### Scenario: 新诊断产物进入 finalize pipeline
- **WHEN** 后续新增 symbol 或 reason diagnostics
- **THEN** 系统 MUST 在 diagnostics 层扩展
- **THEN** facade 文件 SHALL NOT 再重新成为唯一 owner

### Requirement: artifact service 必须保留 stage_funnel 可用性语义
当核心 artifact service 生成 `stage_funnel` lazy section 或 `run_meta.counters.buy_stage_funnel` 时，系统 MUST 原样保留阶段可用性语义。对于没有可靠计数来源的阶段，artifact service MUST 输出 `available=false`，并将对应的 `input_count`、`output_count`、`filtered_count` 保持为 `null`。对于有正式来源且真实计数为 `0` 的阶段，artifact service MUST 保持 `available=true` 且数值为 `0`。

#### Scenario: 聚合 unavailable 阶段
- **WHEN** 上游 `daily_row` 或正式诊断来源无法为某个漏斗阶段提供可靠计数
- **THEN** artifact service SHALL 在 `stage_funnel` 与 `run_meta.counters.buy_stage_funnel` 中将该阶段标记为 `available=false`
- **THEN** artifact service SHALL NOT 将该阶段计数补写为 `0`

#### Scenario: 聚合真实零值阶段
- **WHEN** 上游正式来源明确给出某个漏斗阶段的真实计数为 `0`
- **THEN** artifact service SHALL 保留该阶段 `available=true`
- **THEN** artifact service SHALL 在聚合结果中输出数值 `0`

#### Scenario: lazy section 与 run_meta 语义一致
- **WHEN** 同一个实验同时生成 `stage_funnel` lazy section 与 `run_meta.counters.buy_stage_funnel`
- **THEN** 两个输出面的 `available`、`input_count`、`output_count`、`filtered_count` 语义 SHALL 保持一致
- **THEN** 前端消费任一路径都 SHALL 得到相同的 unavailable/zero 判断结果

