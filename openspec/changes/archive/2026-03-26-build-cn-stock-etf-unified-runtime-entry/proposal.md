## Why

当前前端已经固定了 `cfg_cn_stock_etf_v1` 作为“A股个股 alpha + ETF beta”组合锚点，但系统运行时仍只能单次选择 `cn_a_equity` 或 `cn_etf` 其一，导致该锚点只能作为研究配置存在，不能成为真正的统一运行入口。现在需要把这条锚点推进为正式运行能力，否则前端配置、Governor 语义和实际实验行为会持续错位。

## What Changes

- 新增统一运行入口，使一次实验可以同时运行 `cn_stock_trend_alpha_core` 和 `cn_etf_beta`，并在同一 Governor 下生成组合级结果。
- 新增前端锚点 `cfg_cn_stock_etf_v1` 对应的正式编译语义，使其不再只是可加载模板，而是可执行的统一运行配置。
- 修改运行时配置编译与实验执行链路，使其支持单次运行内的多 sleeve 资产读取、预算裁决和产物收口。
- 修改 Governor、股票 alpha sleeve、ETF beta sleeve 的运行 contract，使其能在同一实验中并行消费统一预算，而不是依赖单 asset_scope 互斥切换。
- 修改 research audit 和结果 snapshot，使统一运行实验可以正式暴露组合级与 sleeve 级诊断、预算与归因摘要。
- **BREAKING**：A 股主线运行入口不再默认假设一次实验只能有单一 `asset_scope` 真相；统一运行实验将以 `governed_a_share` 和 sleeve 级资产上下文作为正式执行真相。

## Capabilities

### New Capabilities
- `cn-stock-etf-unified-runtime-entry`: 定义基于 `cfg_cn_stock_etf_v1` 的统一运行入口，使单次实验可同时运行个股 alpha sleeve 与 ETF beta sleeve，并输出组合级结果。

### Modified Capabilities
- `api-runtime-config-compilation`: 运行前配置编译需要支持由单一前端锚点生成多 sleeve 运行时配置，而不是继续把 `asset_scope` 视为全局单选。
- `experiment-runtime-service`: 实验执行服务需要支持单次请求下的多 sleeve 运行、汇总和产物收口。
- `cn-a-portfolio-governor`: Governor 需要正式管理股票 alpha 与 ETF beta 的并行预算、部署上限和组合级输出。
- `cn-stock-trend-alpha-core`: 股票 alpha sleeve 需要支持在统一实验内作为组合子腿运行，而不是默认占据整次实验的唯一资产上下文。
- `cn-etf-beta-sleeve`: ETF beta sleeve 需要支持在统一实验内与股票 alpha sleeve 并行运行，而不是只在 `asset_scope=cn_etf` 时独占运行。
- `backtest-research-audit`: 研究审计需要新增 unified runtime 的组合级与 sleeve 级 gates、reason codes 和可追溯性要求。
- `results-workbench-snapshot-boundary`: 结果工作台 snapshot 需要正式承载 unified runtime 的组合级摘要与两个 sleeve 的最小解释字段。

## Impact

- 影响后端配置编译与运行入口：
  - `backend/api/backtest_v2`
  - `backend/core/services`
  - `backend/core/tools`
- 影响执行与预算链路：
  - `backend/core/engine_vector`
  - `backend/core/stage_pipeline/adapters`
  - `backend/core/portfolio`
- 影响审计与产物：
  - `backend/core/audit`
  - `backend/api/backtest_v2/artifacts_finalize.py`
- 影响前端结果解释：
  - `frontend/assets/js/backtest_v2.js`
  - `frontend/app/results-workbench`
- 影响前端固定锚点与运行语义：
  - `outputs/configs/cfg_cn_stock_etf_v1.json`
