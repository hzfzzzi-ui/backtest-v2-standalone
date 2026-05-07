# cn-etf-research-entry Specification

## Purpose
Define the minimum A-share ETF research entry, including the controlled first-wave ETF catalog, ETF-specific daily truth tables, and minimal research presets.
## Requirements
### Requirement: 系统必须维护受控的 A 股 ETF 首波研究目录
系统 MUST 为 `cn_etf` 研究入口维护一份正式受控 ETF 目录，且第一阶段目录 MUST 只包含首波 9 只 ETF：`510300.SH`、`510500.SH`、`510050.SH`、`518880.SH`、`511010.SH`、`512100.SH`、`512890.SH`、`588000.SH`、`159915.SZ`。目录 MUST 至少记录 `ts_code`、`symbol`、`name`、`exchange`、`batch_id`、`exposure_bucket`、`list_date` 和 `delist_date`。

#### Scenario: 首波目录写入数据库
- **WHEN** 系统初始化或刷新 `cn_etf` 研究目录
- **THEN** 数据库 MUST 只写入这 9 只 ETF 的正式目录记录
- **THEN** 每条目录记录 MUST 暴露所属批次与资产暴露类别

#### Scenario: 非目录 ETF 不得进入正式研究入口
- **WHEN** 用户请求运行不在首波目录中的 ETF
- **THEN** 系统 MUST 返回显式错误或告警
- **THEN** 系统 SHALL NOT 静默把该 ETF 当成已支持研究资产

### Requirement: 系统必须为 A 股 ETF 建立独立日线真值层与覆盖摘要
系统 MUST 为 `cn_etf` 研究入口建立独立于股票 `V2 canonical` 的 ETF 日线真值层与覆盖摘要。ETF 日线真值层 MUST 至少支持研究执行所需的 `trade_date`、`open`、`high`、`low`、`close`、`volume`、`turnover`、`amount`、`price_adjust_mode` 与 `build_run_id`；覆盖摘要 MUST 至少暴露每只 ETF 的 `coverage_start`、`coverage_end`、`row_count`、`latest_refresh_at` 和 `price_series_semantics`。

#### Scenario: ETF 日线与覆盖摘要独立落库
- **WHEN** 系统刷新首波 ETF 日线数据
- **THEN** ETF 行情 MUST 写入独立 ETF 真值表
- **THEN** 系统 MUST 同步更新覆盖摘要表而不是复用股票侧覆盖逻辑

#### Scenario: 股票主链不得被 ETF 数据污染
- **WHEN** 系统写入 ETF 数据
- **THEN** `pit_security_master` 和 `pams_ohlcv_daily_v2` 的股票正式主链 MUST 保持原有股票口径
- **THEN** ETF 数据 SHALL NOT 被当成股票行写入股票 `V2 canonical`

### Requirement: ETF 研究运行必须显式暴露数据口径与覆盖边界
当 `asset_scope='cn_etf'` 时，系统 MUST 在 `run_meta.json` 或等价研究产物中显式暴露 ETF 研究所用的 ETF 名单、批次、覆盖起止日期、数据表名和价格语义。若价格序列并非完整总收益链，系统 MUST 明确标记该事实。

#### Scenario: 单 ETF 研究运行落盘元信息
- **WHEN** 用户运行单只 `cn_etf` 研究
- **THEN** `run_meta.json` MUST 包含 `asset_scope='cn_etf'`
- **THEN** `run_meta.json` MUST 包含 `etf_symbols`、`coverage_start`、`coverage_end`、`price_series_semantics` 和 `daily_table`

#### Scenario: ETF 研究不得伪装成股票 PIT 研究
- **WHEN** 用户运行 `cn_etf` 研究
- **THEN** 产物 MUST 不再输出股票 PIT 成分股 lineage 文案作为 ETF 真相
- **THEN** ETF 运行摘要 MUST 显式说明其为 ETF 资产研究而非个股 PIT 研究

### Requirement: 系统必须提供首波 ETF 最小研究 preset
系统 MUST 为首波 ETF 提供最小研究 preset，至少包括 `cn_etf_single_asset_template`、`cn_etf_first_wave_core` 和 `cn_etf_first_wave_all`。这些 preset MUST 复用现有研究总线与产物协议，但 SHALL NOT 直接修改 `baseline_V10.x` 的正式个股主逻辑。

#### Scenario: 核心批次 preset 展开
- **WHEN** 用户选择 `cn_etf_first_wave_core`
- **THEN** 系统 MUST 生成仅包含 `510300.SH`、`510500.SH`、`510050.SH`、`518880.SH`、`511010.SH` 和 `512100.SH` 的研究配置
- **THEN** 该研究配置 MUST 保持 ETF 资产上下文而不是回落到 A 股个股上下文

#### Scenario: 全批次 preset 展开
- **WHEN** 用户选择 `cn_etf_first_wave_all`
- **THEN** 系统 MUST 生成包含全部 9 只 ETF 的研究配置
- **THEN** 该配置 MUST 可被实验总线直接消费并产出标准研究产物

### Requirement: cn_etf 研究入口必须支持正式ETF beta sleeve语义
当 `cn_etf` 被 A 股 governed multi-sleeve 主线消费时，系统 MUST 将 `cn_etf` 研究入口明确标记为 `cn_etf_beta` 的正式来源之一，而 SHALL NOT 继续把它仅视为孤立的 ETF research entry。

#### Scenario: ETF 研究入口进入 governed 主线
- **WHEN** Governor 启用 `cn_etf_beta` sleeve
- **THEN** 系统 MUST 允许从 `cn_etf` 研究入口解析正式 ETF beta 候选池
- **THEN** 相关产物 MUST 将该入口标识为 beta sleeve 来源而不是独立旁路实验

### Requirement: cn_etf 研究入口必须暴露Phase 1 core beta范围
当 `cn_etf` 服务于 `cn_etf_beta` Phase 1 时，研究入口 MUST 显式暴露 core beta 范围：
- `510300.SH`
- `510500.SH`
- `510050.SH`
- `512100.SH`

并 MAY 显式暴露 `512890.SH` 为 limited defense candidate。

#### Scenario: 研究入口返回 core beta 范围
- **WHEN** 系统为 `cn_etf_beta` 构建 Phase 1 候选池
- **THEN** 入口摘要 MUST 明确哪些 ETF 属于正式 core beta 范围
- **THEN** 入口摘要 MUST 明确 `512890.SH` 是否作为 limited defense candidate 参与

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

### Requirement: cn_etf research entry MUST 支持 ETF research mainline R1 preset
`cn_etf` research entry MUST 支持装载 `etf/cn_broad_based_research_mainline_r1`，并将其视为受控目录内的 research-only study preset。该 preset MUST 可由 `study_runner` 与 generated thin script 直接执行。

#### Scenario: study_runner 装载 R1 preset
- **WHEN** 用户通过 study id `etf/cn_broad_based_research_mainline_r1` 运行研究
- **THEN** 系统 MUST 能从 `research/studies/etf/` 装载对应 study yaml
- **THEN** 系统 MUST 生成可直接执行的 request payload

#### Scenario: generated thin script 指向 R1 preset
- **WHEN** 用户运行 `backend/scripts/generated/run_etf_cn_broad_based_research_mainline_r1.py`
- **THEN** 脚本 MUST 将执行入口转发到 `study_run etf/cn_broad_based_research_mainline_r1`
- **THEN** 脚本 SHALL NOT 内嵌策略实现逻辑

