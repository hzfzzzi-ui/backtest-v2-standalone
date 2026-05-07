## Why

当前 CN ETF 主线使用 `price_only_not_total_return + adj_factor` 的混合口径：分红只体现在 HFQ 估值里，没有显式现金事件，导致 `511010` 一类防守 ETF 的分红链路不可审计，也让卖出回款与持仓估值之间存在口径断裂。现在需要把 ETF 现金分红从“隐含在估值里”改成“正式记账事件”，让 NAV、cash 与审计口径闭合。

## What Changes

- 为 CN ETF 新增正式分红事件数据接入口，落到独立 side table，并通过 provider / data bundle 正式暴露给回测主路径。
- 为 ETF 持仓增加显式现金分红记账：在除息日确认分红权益，并按配置选择直接入账 cash 或先记入 receivable、到账日再转入 cash。
- 在显式分红事件生效时，对 ETF 持仓估值基线做中性化处理，避免继续从 HFQ 估值里重复吃到同一笔分红。
- 扩展 execution / accounting audit，使现金守恒、NAV 一致性和样本输出能识别分红应收与到账。

## Capabilities

### New Capabilities
- `etf-dividend-cash-events`: 定义 CN ETF 显式分红事件的数据合同、除息/到账生命周期与运行时记账行为。

### Modified Capabilities
- `market-data-access-contract`: 统一市场数据访问层需要正式提供 ETF 分红事件读取与审计回显。
- `price-adjustment`: 显式分红事件启用后，ETF HFQ 估值必须避免与现金分红重复计入。
- `backtest-audit`: 现金守恒与 NAV 审计需要纳入分红现金流和分红应收。
- `accounting-integrity-audit`: 主线会计完整性审计需要验证分红应收创建、到账结转与账面闭环。

## Impact

- 影响模块：`backend/cli/managed/refresh_cn_etf_daily.py`、`backend/core/data/*`、`backend/core/tools/data_bundle_builder.py`、`backend/core/stage_pipeline/adapters/*`、`backend/core/portfolio/nav_snapshot.py`、`backend/core/audit/experiment_audit.py`、相关单测。
- 影响资产范围：仅 `cn_etf` 主线，不改股票腿、不改前端展示层。
- 风险：若只加现金不做估值基线中性化，会双重计数分红；若只做 pay-date 入账不加 receivable，会在 ex-date 到 pay-date 之间扭曲 NAV。
