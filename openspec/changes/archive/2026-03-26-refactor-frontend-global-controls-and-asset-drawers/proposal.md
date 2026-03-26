## Why

当前前端页面仍以 `S1-S9` 研究阶段为主导航，左侧同时承载全局市场状态、总仓位控制和资产特化参数，已经和当前 A 股 governed 多 sleeve 架构脱节。随着 `market_regime_engine`、`global_portfolio_governor`、`cn_stock_trend_alpha_core` 和 `cn_etf_beta` 的 contract 成型，前端必须把“全局通用控制”和“资产特化配置”分层，否则页面会持续拥挤且难以解释。

## What Changes

- 新增顶部全局控制层，用统一入口承载资产范围、时间范围、`Regime` 和 `Governor` 摘要与编辑入口。
- 新增资产范围驱动的左侧特化抽屉布局；当资产范围切换为 A 股个股或 A 股 ETF 时，左侧仅显示对应资产的特化配置，而不再混入全局市场状态和总仓位控制。
- 调整中间结果区布局，明确拆分 `Performance / Regime / Governor / Attribution` 四类结果视图。
- 让 ETF 模式在前端具有正式的 `cn_etf_beta` 语义，而不是继续借用“股票池 / 个股排序 / PIT”文案。
- **BREAKING**：左侧主导航不再以 `S1-S9` 研究阶段作为唯一主组织方式，页面正式改为“顶部全局控制 + 左侧资产特化抽屉 + 中间结果面板”的结构。
- **BREAKING**：`Regime` 与 `Governor` 不再作为资产特化配置的一部分暴露在左侧阶段面板中，而是上移为全局公共控制层。

## Capabilities

### New Capabilities
- `frontend-global-control-strip`: 定义桌面研究台顶部全局控制层，用于统一承载资产范围、时间范围、Regime 和 Governor 的摘要与编辑入口。
- `frontend-asset-scoped-drawers`: 定义按 `asset_scope` 切换的左侧特化抽屉布局，只暴露当前资产或 sleeve 的特化配置。

### Modified Capabilities
- `results-workbench-snapshot-boundary`: 扩展结果工作台 snapshot 语义，使其正式支持 `Performance / Regime / Governor / Attribution` 四类结果面板。
- `cn-etf-research-entry`: 调整 ETF 前端入口语义，使 `cn_etf` 页面正式表达 `cn_etf_beta` 的特化配置，而不是沿用股票研究台文案。
- `multi-asset-entry-boundaries`: 扩展资产切换的前端边界语义，使 `asset_scope` 切换不仅改变数据上下文，也驱动资产特化抽屉与顶部全局控制层。

## Impact

- 影响前端主入口与过渡层：
  - `frontend/index.html`
  - `frontend/assets/js/backtest_v2.js`
  - `frontend/assets/js/ui-controls.js`
  - `frontend/assets/js/state/config-draft-core.js`
- 影响结果工作台与 snapshot 消费层：
  - `frontend/app/results-workbench/**`
  - `frontend/assets/js/artifacts.js`
- 影响配置草稿与页面状态组织方式，但不直接改变后端研究逻辑或运行 contract。
