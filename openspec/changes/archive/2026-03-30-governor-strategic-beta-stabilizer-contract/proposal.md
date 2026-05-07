## Why

当前系统里，Governor 仍主要向 ETF sleeve 下发单一 `target_exposure`，而 formal `cn_etf_beta` 仍被定义成受预算约束的低频配置引擎。这套定义更适合“beta 承接/减配”，不适合“长期战略底仓 + 弱市受控定投 + 有限防守”的 beta 稳定器目标。

与此同时，仓库里已经存在 `CN_STOCK_ETF_50_50` 研究组合装配器，但它是 research-only 的等权假设，不是正式 Governor 合同。如果不先在 spec 层把 Governor 与 ETF 的职责重新定义清楚，后续继续讨论仓位配比、弱市加仓、CAGR 或 denominator 都会继续混淆研究假设与正式主线。

## What Changes

- 重新定义 Governor 为组合级风险与预算宪法，要求其面向 sleeve 输出分层预算，而不再只输出单一目标仓位。
- 要求 Governor 至少区分 `strategic_floor_cap`、`tactical_overlay_cap`、`deployment_pace`、`hard_block_flags` 与 `defense_bias`，并把这些字段纳入正式预算证据链。
- 重新定义 formal `cn_etf_beta` 的目标角色为“长期 beta 稳定器”，要求其显式拆分 `core_accumulator`、`tactical_satellite`、`limited_defense` 三层，而不是继续把所有 ETF 目标都当成单层 tactical allocation。
- 明确弱市语义：`LIGHT / TRANS_DOWN` 先收缩 overlay，再决定是否允许 paced accumulation；`RISK_OFF` 默认是 floor-only 或 floor+defense 过渡，而不是默认清零；只有 Governor 显式硬阻断时才允许停止新增风险或强制去杠杆。
- 明确固定 `50/50` 的 stock/ETF 组合权重只能作为 research combo 假设存在，不得被解释为正式 Governor 预算真相。
- 扩展 research audit 与 ETF 产物，使其能够解释 strategic floor、overlay、deployment pace、hard block 与 actual exposure 之间的关系。

## Capabilities

### New Capabilities

### Modified Capabilities

- `cn-a-portfolio-governor`: Governor 的正式预算合同需要从单层 target 扩展为战略底仓、战术 overlay、部署节奏与硬阻断信号。
- `cn-etf-beta-sleeve`: ETF sleeve 的正式角色、弱市语义、资产角色拆分与产物输出需要升级为长期 beta 稳定器口径。
- `backtest-research-audit`: 审计必须能够区分正式 Governor 合同与 research combo 假设，并显式归因 floor、overlay、hard block 与定投节奏。

## Impact

- 影响 `backend/core/config/cn_a_governed_mainline.py`、`backend/core/config/etf_beta_contract.py`、`backend/core/engine_vector/cn_etf_beta_signal_provider.py`、`backend/core/audit/research_audit.py` 及相关测试。
- 影响 `run_meta.json`、`audit.json`、`portfolio_daily.csv`、`orders.csv`、ETF 诊断 summary 的字段定义与解释方式。
- 影响 `backend/core/services/cn_stock_etf_unified_runtime_service.py` 的定位与标记方式，但本 change 不要求立即重写 research combo 的收益拼接逻辑。
- 不在本 change 中直接修改 ETF 正式资产池，不直接修改 denominator，也不承诺收益优化或策略胜出。
