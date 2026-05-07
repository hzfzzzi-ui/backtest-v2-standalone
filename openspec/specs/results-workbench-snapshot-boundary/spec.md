# results-workbench-snapshot-boundary Specification

## Purpose

定义 `ResultsWorkbenchSnapshot` 作为结果工作台唯一输入真相的正式边界。
## Requirements
### Requirement: 结果工作台 MUST 只消费 snapshot

桌面结果工作台 MUST 只消费 `ResultsWorkbenchSnapshot` 作为唯一输入真相。

#### Scenario: 页面壳加载实验结果
- **WHEN** 页面壳完成主 surface 与子面的获取
- **THEN** 页面壳组装 `ResultsWorkbenchSnapshot`
- **THEN** Vue workbench 只通过 snapshot 渲染结果

### Requirement: 页面壳 MUST 采用 fetch-build-push 单向模型

页面壳 MUST 采用 `fetch -> build snapshot -> push snapshot` 的单向桥接模型。

#### Scenario: 子面懒加载完成
- **WHEN** 页面壳完成 `nav`、`symbol_stats` 或其他子面加载
- **THEN** 页面壳重建 snapshot 并推送给工作台

### Requirement: Snapshot MUST 携带 assetContext

系统 MUST 在 `ResultsWorkbenchSnapshot` 中提供统一的 `assetContext`，作为工作台展示的正式资产真相。

#### Scenario: 切换实验时更新资产上下文
- **WHEN** 用户切换到另一个实验
- **THEN** 页面壳连同结果 snapshot 一起更新 `assetContext`

### Requirement: Snapshot MUST 携带正式结果摘要

当结果属于 unified combo、Governed A 股或 ETF 研究结果时，snapshot MUST 直接携带相应的正式摘要字段，供工作台渲染。

#### Scenario: 渲染组合结果
- **WHEN** 页面壳加载 unified combo 结果
- **THEN** snapshot 携带 `comboTruth`、正式 regime 摘要与 governor 摘要

### Requirement: results snapshots MUST explain runtime behavior from execution truth first

结果工作台 snapshot MUST 优先使用 `execution_contract` 或 `execution_contract_ref` 解释本次运行行为，不得让 provenance 或旧镜像字段重新成为主真相。

#### Scenario: building a unified combo results snapshot
- **WHEN** 页面壳或 helper 组装 unified combo 的 `ResultsWorkbenchSnapshot`
- **THEN** 运行行为说明 MUST 来自 `execution_contract` 或 `execution_contract_ref`
- **THEN** provenance 只可用于解释合同来源
- **THEN** `comboTruth` 只可用于展示摘要

### Requirement: results snapshots MUST treat legacy source contracts as explanatory fallbacks only

如果结果层仍读取旧 `component_source_contract` 或其它 legacy 镜像，该读取 MUST 被限制为说明或兼容用途。

#### Scenario: reading a legacy combo artifact
- **WHEN** helper 在旧实验结果中找不到独立 `execution_contract.json`
- **THEN** helper MAY 使用 legacy 合同恢复说明信息
- **THEN** helper SHALL NOT 把 legacy source contract 标记为正式执行真相

