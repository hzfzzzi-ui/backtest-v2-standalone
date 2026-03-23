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
