## Why

当前 A 股 ETF 研究已经证明两件事：一是旧 ETF V1 / 稳定器线在长期上收益接近打平，不能作为正式 ETF 主线；二是模板 A 的 A0 胜出版虽然比旧线更像样，但实际暴露仍偏低，且它还沿用了过多接近个股 alpha 的收缩语义。现在需要把研究问题重新收敛为：在同一个 Governor 之下，只针对宽基 ETF sleeve 设计一套更符合配置层职责的暴露政策，而不是继续把宽基 ETF 和行业 ETF、个股 alpha 混在同一套响应函数里。

## What Changes

- 新增“宽基 ETF Governor 暴露政策”研究能力，只研究宽基 ETF sleeve 在 `BULL / TRANS_UP / LIGHT / TRANS_DOWN / RISK_OFF` 下的目标暴露、最低可部署暴露、分层承接与 fallback 语义。
- 明确区分 Governor 的统一环境真相与宽基 ETF sleeve 的本地暴露翻译：Governor 继续统一输出状态与总风险约束，但宽基 ETF sleeve 不再默认沿用个股 alpha 式的快速收缩政策。
- 在 ETF beta sleeve 中收敛“宽基配置层”角色：允许在 `LIGHT` 与受控 `TRANS_DOWN` 环境下保留或分层承接宽基 beta，但仍必须服从 Governor 的总风险边界与 `RISK_OFF` 约束。
- 新增宽基 ETF 暴露政策的最小研究对照，比较不同 target exposure / min deployable / layering / fallback 组合，而不扩候选池、不引入行业 ETF。
- **BREAKING**：`cn_etf_beta` 的正式研究解释从“统一 ETF sleeve 响应函数”收敛为“当前 change 仅覆盖宽基 ETF sleeve 响应函数”，行业 ETF 不属于本轮正式范围。

## Capabilities

### New Capabilities
- `cn-broad-based-etf-governed-exposure-policy`: 定义宽基 ETF sleeve 在 Governor 统一状态下的独立暴露政策、分层承接规则、fallback 语义与最小研究对照边界。

### Modified Capabilities
- `cn-etf-beta-sleeve`: 将 ETF beta sleeve 的正式研究重心收敛到宽基 ETF 配置层，并允许宽基 ETF 使用不同于个股 alpha 的暴露翻译。
- `cn-a-portfolio-governor`: 明确 Governor 统一输出环境真相，但允许宽基 ETF sleeve 使用与个股 alpha 不同的本地暴露政策，同时保持总风险边界一致。
- `backtest-research-audit`: 为宽基 ETF 暴露政策研究补充 target/actual exposure、layered deployment、fallback usage 与 under-deploy 归因证据。
- `cn-etf-research-entry`: 明确本轮正式研究入口只覆盖宽基 ETF sleeve，不引入行业 ETF preset 或行业 ETF 正式候选范围。

## Impact

- 影响模块：
  - `backend/core/config`
  - `backend/core/engine_vector`
  - `backend/core/audit`
  - `backend/api/backtest_v2`
  - `research/studies/etf`
  - `tests/unit`
- 影响系统：
  - 宽基 ETF sleeve 的 Governor 暴露语义
  - ETF research audit 证据链
  - ETF 研究入口与 preset 边界
- 不在本轮范围：
  - 行业 ETF
  - 个股 alpha 主逻辑
  - unified runtime 组合配比
  - 宽基 ETF 候选池扩张
