## Why

当前 formal `cn_etf_beta` Phase 1 已经按原始文档收口为三桶配置引擎，但运行链路仍保留了基于状态的硬编码 `slot_cap` 退出语义，导致 `TRANS_DOWN / RISK_OFF` 被直接翻译成 `NO_TRADE`，覆盖了正式文档要求的“缩减权益 + limited defense + cash buffer”配置语义。这个偏差已经影响 formal mainline 的行为解释，必须先在 spec 层把 boundary policy 对齐，再讨论收益或承接增强。

## What Changes

- 明确 formal ETF Phase 1 的本地 boundary policy 必须以 Governor 下发预算、执行 flags 与三桶配置语义为准，而不是由硬编码状态槽位表直接决定 `NO_TRADE`。
- 明确 `RISK_OFF` 在 formal Phase 1 中的默认语义是缩减配置与防守过渡，不得被静默等同为零目标、零部署、零交易；只有 Governor 明确禁止新风险或要求去杠杆时，才允许执行硬性收缩。
- 明确 `TRANS_DOWN` 不属于当前 formal Phase 1 的受控承接研究范围；formal mainline 先要求边界与文档一致，不在本 change 中引入新的 controlled accumulation 语义。
- 要求 research audit 对 formal ETF Phase 1 明确拆分 “Governor 边界” 与 “ETF 本地 boundary 决策”，避免再次把局部 `slot_cap` 误解释成上游总控真相。

## Capabilities

### New Capabilities

### Modified Capabilities
- `cn-etf-beta-sleeve`: formal Phase 1 的 boundary policy、RISK_OFF 配置语义和本地 deployability 解释需要收口到原始文档定义。
- `backtest-research-audit`: Governed A 股实验中的 formal ETF Phase 1 审计需要显式区分 Governor 下发边界与 ETF 本地 boundary 决策。

## Impact

- 影响 `backend/core/config/etf_beta_contract.py`、`backend/core/engine_vector/cn_etf_beta_signal_provider.py`、ETF formal study 配置与对应单测。
- 影响 `research_audit` / attribution 相关产物字段与 formal ETF 主线说明文案。
- 不改变 ETF 正式资产池，不改变上游 `market_regime_engine` 真相源，不引入行业 ETF、收益优化或新的 controlled accumulation 研究口径。
