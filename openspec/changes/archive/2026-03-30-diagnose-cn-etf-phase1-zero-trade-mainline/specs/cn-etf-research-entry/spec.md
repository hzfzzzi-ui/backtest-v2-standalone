## ADDED Requirements

### Requirement: 正式 ETF Phase 1 研究入口必须支持零交易诊断模式
`cn_etf_phase1_allocation_entry` MUST 提供一条不改变正式策略口径的诊断模式，用于输出正式资产池、正式参数和逐层对照实验的根因诊断产物。

#### Scenario: 诊断模式复用正式口径
- **WHEN** 用户运行正式 ETF Phase 1 的零交易诊断模式
- **THEN** 系统 MUST 复用正式资产池、正式 Governor 输入和正式配置 contract
- **THEN** 系统 SHALL NOT 因诊断模式自动切换到研究分支资产或研究排序壳

### Requirement: 正式 ETF Phase 1 研究入口必须输出可复现的诊断产物清单
诊断模式 MUST 输出可复现的调仓日明细、链路样本、逐层对照实验结果和关键参数生效值清单，以支持离线复核。

#### Scenario: 诊断产物齐全
- **WHEN** 正式 ETF Phase 1 诊断模式运行完成
- **THEN** 产物目录 MUST 包含调仓日明细、链路样本和逐层对照实验汇总
- **THEN** `run_meta` 或等价元信息 MUST 记录本次诊断使用的正式 study、正式资产池和参数快照
