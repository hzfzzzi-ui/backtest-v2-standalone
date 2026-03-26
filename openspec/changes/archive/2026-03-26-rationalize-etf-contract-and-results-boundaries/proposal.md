## Why

当前代码主干没有失控，但已经出现三类明显的边界债务：ETF contract 在 schema / governed config / provider / artifacts / audit 多处手工透传，前端结果页仍在客户端补算和拼装部分研究真相，旧桌面壳与 Vue workbench 仍存在双 owner。继续在这些边界上叠加 ETF、组合和前端能力，会提高字段漂移、结果解释不一致和回归难度。

现在收口这些边界，是为了在不改变研究口径的前提下，先恢复单一真相源、单一 owner 和更清晰的模块职责，再继续推进 unified runtime、ETF 正式主线和前端收敛。

## What Changes

- 新增 ETF contract owner 边界，明确 ETF beta 配置归一化、运行时摘要、artifact 投影和 audit 引用的唯一正式宿主。
- 将结果工作台和 research combo 的结果真相继续下沉到后端 surface / snapshot，前端不再重算 market state、regime 语义或客户端拼装伪 snapshot。
- 收紧前端旧壳边界，明确 `backtest_v2.js`、`ui-controls.js`、`artifacts.js` 只允许保留 bootstrap、桥接和兼容职责。
- **BREAKING**：禁止新增 ETF contract 字段时继续采用“schema -> provider -> artifact -> audit 多点手工透传”的模式。
- **BREAKING**：禁止前端从 `dailyRows`、`market_state`、`trade_mode` 或组件实验产物自行反推正式 regime / governor / combo 语义。
- **BREAKING**：research combo 结果必须有后端 canonical truth surface，前端不得继续以拼接快照作为正式解释来源。

## Capabilities

### New Capabilities
- `etf-contract-owner-boundary`: 定义 ETF beta contract 的单一宿主、投影边界和下游消费方式。

### Modified Capabilities
- `cn-etf-beta-sleeve`: 收紧 ETF beta 配置、provider、artifact 和 audit 的 contract owner 规则。
- `results-workbench-snapshot-boundary`: 要求结果工作台和 research combo 只消费后端生成的 canonical snapshot / surface 真相。
- `frontend-module-split`: 继续收紧旧桌面壳与 Vue workbench 的 owner 边界，阻止旧壳继续吸收结果语义和活跃逻辑。
- `backtest-research-audit`: research audit 必须只引用统一 ETF contract / combo truth，而不是重复投影或前端补算语义。

## Impact

- 后端：
  - `backend/api/backtest_v2`
  - `backend/core/config`
  - `backend/core/engine_vector`
  - `backend/core/audit`
  - `backend/core/services`
- 前端：
  - `frontend/assets/js/backtest_v2.js`
  - `frontend/assets/js/ui-controls.js`
  - `frontend/assets/js/artifacts.js`
  - `frontend/app/results-workbench/*`
- 产物与接口：
  - `ResultsWorkbenchSnapshot`
  - experiment surface / section
  - `run_meta.json`
  - `audit.json`
- 不在本轮范围：
  - ETF 新规则族
  - unified runtime 正式实现
  - baseline 主逻辑与 A 股个股 alpha 口径调整
