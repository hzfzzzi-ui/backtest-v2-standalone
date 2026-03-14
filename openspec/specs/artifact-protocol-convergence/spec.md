# artifact-protocol-convergence Specification

## Purpose
TBD - created by syncing change protocol-contract-convergence. Update Purpose after archive.
## Requirements
### Requirement: 协议标准命名必须唯一
系统 MUST 采用唯一 canonical 产物命名与字段命名，禁止同一语义出现多个标准名。

#### Scenario: 产物命名标准化
- **WHEN** 系统写出实验产物
- **THEN** 原因码聚合文件 SHALL 使用 `reason_codes.csv` 作为标准文件名
- **THEN** `group_files.reason_codes` SHALL 指向 `reason_codes.csv`

#### Scenario: run_meta counters 字段标准化
- **WHEN** 系统写出 `run_meta.json`
- **THEN** `counters` SHALL 使用短名字段：`raw_signal`, `blocked`, `orders`, `skipped`, `closed_trades`
- **THEN** 新写出数据 SHALL NOT 使用 `_count` 作为标准字段名

### Requirement: 读取侧必须提供两版本兼容窗口
系统 MUST 在两个版本窗口内兼容读取 legacy 文件名与 legacy counters 字段名。

#### Scenario: 兼容 legacy 原因码文件名
- **WHEN** 标准文件 `reason_codes.csv` 不存在但 legacy 文件 `reason_code_counts.csv` 存在
- **THEN** 读取流程 SHALL 回退读取 `reason_code_counts.csv`
- **THEN** 上层消费方 SHALL 获得与标准文件等价的数据结构

#### Scenario: 兼容 legacy counters 字段
- **WHEN** `run_meta.counters` 中仅存在 `_count` 命名字段
- **THEN** 读取流程 SHALL 映射为短名字段进行消费
- **THEN** 前端与 API 返回 SHALL 继续输出短名口径

### Requirement: 缺失产物必须降级为可观测空产物
系统 MUST 在产物缺失时生成空文件并记录缺失来源，避免流程中断与静默失败。

#### Scenario: 产物源缺失
- **WHEN** 某标准产物无法从运行结果推导
- **THEN** 系统 SHALL 写出对应空产物文件（合法格式）
- **THEN** `run_meta.missing_fields` SHALL 记录稳定键名的缺失来源

#### Scenario: 下游消费空产物
- **WHEN** 前端或 API 读取到空产物
- **THEN** 系统 SHALL 返回空行或默认结构，不抛出协议错误
- **THEN** 状态中心或诊断信息 SHALL 可见缺失说明

### Requirement: artifact 稳定化 owner 必须集中到核心 service
artifact 协议的稳定化和标准产物补齐 MUST 由核心 artifact service 统一负责。endpoint 层 MAY 提供 HTTP 包装，但 SHALL NOT 成为稳定化的唯一 owner。

#### Scenario: manifest 写入
- **WHEN** 实验完成并需要写入 manifest
- **THEN** manifest SHALL 由核心 artifact service 生成

#### Scenario: 标准产物补齐
- **WHEN** 系统需要补齐 `perf.json`、`nav.csv`、`run_meta.json`、`audit.json`
- **THEN** 这些动作 SHALL 由核心 artifact service 负责

### Requirement: report.html 不再属于当前 artifact 主契约
系统当前 artifact 主契约 MUST 以 `manifest.json`、`perf.json`、`nav.csv`、`run_meta.json`、`audit.json`、Markdown 分析报告等产物为核心。`report.html` 若存在，仅可视为 legacy artifact，当前主契约 SHALL NOT 继续依赖它。

#### Scenario: 新实验稳定化
- **WHEN** 系统稳定化一个新实验目录
- **THEN** manifest SHALL NOT 将 `report.html` 标记为当前标准产物

#### Scenario: 历史实验目录仍保留 report.html
- **WHEN** 历史实验目录中仍存在 `report.html`
- **THEN** 系统 MAY 兼容保留文件
- **THEN** 当前前端与门禁 SHALL NOT 依赖该文件
