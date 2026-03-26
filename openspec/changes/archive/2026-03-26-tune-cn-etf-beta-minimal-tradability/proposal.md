## Why

`cn_etf_beta` 的 provider/read path、Governor 真值和最小 smoke 路径已经打通，但当前 `cn_etf_first_wave_core` 主线仍是 `0 trades`。事实说明 ETF 资产已经进入主线语义，却还没有真正具备最小可交易能力；如果继续在这条线上叠加 Governor、前端和多资产逻辑，后续结果会变成“路径通过、策略不工作”。

## What Changes

- 为 `cn_etf_beta` 定义最小可交易规则，使其在不复制股票 breakout 壳的前提下，具备独立、低频、可解释的 ETF beta 选标与调仓逻辑。
- 为 Governor 增加 `cn_etf_beta` 的状态到预算/槽位映射，避免 ETF beta 再次静默继承股票 alpha 的 `NO_TRADE` 和本地约束语义。
- 为 `research_audit` 增加 `cn_etf_beta` 最小可交易 smoke gate，要求主 smoke 不仅路径通过，还要有非零交易证据。
- **BREAKING**：`cn_etf_beta` 的 Phase 1 运行路径不再复用股票 breakout 候选与局部 budget 控制语义。
- **BREAKING**：`cn_etf_beta` 的正式 smoke 验收从“路径通过即可”提升为“路径通过且存在最小可交易证据”。

## Capabilities

### New Capabilities
- 暂无

### Modified Capabilities
- `cn-etf-beta-sleeve`: 增加最小可交易规则、低频调仓框架和正式 smoke 验收要求。
- `cn-a-portfolio-governor`: 增加 ETF beta 的五状态部署映射，明确 ETF beta 不复用股票 alpha 的局部 budget 语义。
- `backtest-research-audit`: 增加 `cn_etf_beta` 最小可交易 smoke gate 和对应 reason-code 证据要求。

## Impact

- 影响代码：
  - `backend/core/engine_vector`
  - `backend/core/stage_pipeline/adapters`
  - `backend/core/tools`
  - `backend/core/audit`
  - `backend/api/backtest_v2`
  - `research/studies/etf`
- 影响产物：
  - `run_meta.json`
  - `audit.json`
  - `orders.csv`
  - `reason_codes.csv`
  - ETF smoke 结论摘要
- 不涉及：
  - 新增 ETF 名单
  - 防守层和保险层接入
  - A 股股票 `V2 canonical` 数据口径变更
