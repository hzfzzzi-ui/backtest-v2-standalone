## Why

当前 ETF 子系统的正式运行链路仍然混合了两类语义：一类是执行与正式审计必须依赖的正式真相，另一类是研究排障用的中间预算、节奏、缺口和解释字段。这种混合已经在过去多次引发口径漂移、正式产物误读和执行边界反复污染，因此现在需要把 ETF 私有合同和正式审计/研究诊断边界彻底收紧。

## What Changes

- 收敛 ETF 子系统的正式输出，只保留进入共享执行链和正式审计所必需的正式真相。
- 明确 ETF 私有中间语义中的研究字段只允许停留在子系统内部或研究诊断层，不再进入正式执行合同和正式审计真相。
- **BREAKING** 调整 ETF 正式产物中的字段边界，移除或迁移不应继续作为正式真相暴露的私有预算、节奏、缺口和解释字段。
- 收敛 `research_audit` 对 ETF 的职责，只负责研究归因和排障解释，不再承担正式运行合同的定义职责。
- 更新系统架构文档与共享接口文档，使文档中的 ETF 边界与当前正式运行链一致。

## Capabilities

### New Capabilities

- 无

### Modified Capabilities

- `architecture-doc`: 当前正式模块边界必须明确区分 ETF 正式合同、正式审计与研究诊断职责。
- `cn-etf-beta-sleeve`: ETF 子系统的正式输出必须收敛为最终可执行与可正式审计的真相，研究中间字段不得继续冒充正式合同。
- `runtime-boundary-contracts`: 共享运行时合同必须明确 ETF 私有中间语义不能直接进入正式执行与正式产物边界。
- `backtest-research-audit`: research audit 必须只消费并解释 ETF 研究证据，不得继续与正式审计真相混层。

## Impact

- 受影响代码主要在 ETF 私有层与审计层：
  - `backend/core/config/etf_beta_contract.py`
  - `backend/core/engine_vector/cn_etf_beta_signal_provider.py`
  - `backend/core/stage_pipeline/adapters/daily_accounting.py`
  - `backend/core/audit/research_audit.py`
- 受影响正式文档：
  - `docs/02_系统架构设计/全系统架构设计.md`
  - `docs/01_系统接口模块定义/共享层/A股子系统接口模块定义.md`
- 受影响产物与消费者：
  - `audit.json`
  - `portfolio_daily.csv`
  - 任何直接消费 ETF 正式诊断字段的研究脚本或前端展示
