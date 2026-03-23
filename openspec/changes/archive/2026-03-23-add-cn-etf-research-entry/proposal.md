## Why

当前系统已经证明 A 股个股 `CSI1000 PIT` 在 `V10.2` 壳下存在明显的小盘执行脆弱性，但本地数据库和研究入口仍然只面向股票，无法用 A 股 ETF 快速验证“更适合作为多资产主线入口的 beta 暴露”这条路径。现在需要先用最小改造把 A 股 ETF 接进数据库、前后端入口和研究主线，建立一条可审计、可回滚、可与当前个股主线并行对照的 ETF 研究路径。

## What Changes

- 新增 A 股 ETF 最小研究入口资产层，定义正式 `cn_etf` 资产范围，并将首批 9 只 ETF 纳入受控接入名单。
- 新增 A 股 ETF 数据库最小链路，包括 ETF 基础主数据、日线真值表和覆盖/刷新摘要，支持手动或受控刷新研究所需窗口。
- 扩展运行时编译、universe 入口和研究配置，使 `cn_etf` 能以单标的 `CUSTOM` 和轻量预设组合方式进入回测，而不复用 A 股个股过滤语义。
- 扩展前后端页面，让研究台能显式选择 A 股 ETF 资产范围、展示 ETF 候选清单和 ETF 专属提示，而不再把股票池文案当成默认真相。
- 明确第一阶段不做内容：
  - 不改现有 `baseline_V10.x` 个股主逻辑
  - 不把 ETF 混入 `pams_ohlcv_daily_v2` 个股 canonical 主链
  - 不一次性做完整 ETF 平台化或全市场 ETF 覆盖

## Capabilities

### New Capabilities
- `cn-etf-research-entry`: 规范 A 股 ETF 的最小数据库接入、研究入口、首批 ETF 名单、运行约束与验收口径。

### Modified Capabilities
- `multi-asset-entry-boundaries`: 新增 `cn_etf` canonical asset scope，并要求系统显式区分 A 股个股与 A 股 ETF 入口。
- `universe-resolver`: 让 resolver 在 `cn_etf` 下支持 ETF `CUSTOM` 单标的和受控 ETF 预设组合，而不继续复用 A 股股票池语义。
- `results-workbench-snapshot-boundary`: 让桌面研究页和结果工作台能按 ETF 资产上下文显示研究入口、提示文案和结果摘要。

## Impact

- 数据库与刷新链：
  - `backend/cli/managed`
  - `backend/core/data`
  - `docs/db`
- 运行时与研究入口：
  - `backend/core/config`
  - `backend/core/tools`
  - `backend/core/universe`
  - `backend/api/backtest_v2`
  - `research/studies`
- 前端页面与资产上下文：
  - `frontend/index.html`
  - `frontend/assets/js/pages`
  - `frontend/assets/js/state`
  - `frontend/assets/js/backtest_v2.js`
