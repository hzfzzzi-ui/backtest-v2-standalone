## ADDED Requirements

### Requirement: 系统必须提供 A股个股+ETF 的统一运行入口
系统 MUST 提供 `cn-stock-etf-unified-runtime-entry` 能力，使单次实验可以基于同一份前端锚点配置同时运行 `cn_stock_trend_alpha_core` 和 `cn_etf_beta`，并在同一 Governor 下输出组合级结果。系统 SHALL NOT 再要求用户必须先运行两次独立实验再手工拼接 NAV，才能得到“个股 alpha + ETF beta”的正式组合结果。

#### Scenario: 基于前端锚点发起统一运行
- **WHEN** 用户使用 `cfg_cn_stock_etf_v1` 或等价 unified runtime 配置发起实验
- **THEN** 系统 MUST 在同一次实验中同时拉起股票 alpha sleeve 和 ETF beta sleeve
- **THEN** 系统 MUST 产出统一实验 ID、组合级产物和 sleeve 级摘要

#### Scenario: 统一运行不再退化为后处理拼接
- **WHEN** 系统完成 unified runtime 实验
- **THEN** 组合级 `nav/perf/run_meta/audit` MUST 来自同一实验运行链路
- **THEN** 系统 SHALL NOT 仅通过读取两次历史实验结果后处理生成组合真相

### Requirement: 统一运行入口必须区分组合级与 sleeve 级资产上下文
统一运行入口 MUST 同时表达组合级资产上下文与 sleeve 级资产上下文。组合级上下文 SHALL 表示“Governed A股多 sleeve 主线”，而股票 alpha 与 ETF beta SHALL 各自保留独立 `asset_scope` 真相。系统 SHALL NOT 用单一全局 `asset_scope` 覆盖两个 sleeve 的真实读表与执行语义。

#### Scenario: 组合级上下文驱动统一实验
- **WHEN** 系统编译 unified runtime 实验
- **THEN** 组合级上下文 MUST 能表达该实验包含多个 sleeve
- **THEN** Governor、audit 和 snapshot MUST 消费该组合级上下文

#### Scenario: sleeve 级上下文保留真实资产语义
- **WHEN** 股票 alpha sleeve 与 ETF beta sleeve 在同一次实验中并行运行
- **THEN** 股票 alpha sleeve MUST 继续使用 `cn_a_equity` 读表与运行语义
- **THEN** ETF beta sleeve MUST 继续使用 `cn_etf` 读表与运行语义
