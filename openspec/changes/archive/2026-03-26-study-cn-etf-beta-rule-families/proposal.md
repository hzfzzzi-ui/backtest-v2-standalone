## Why

当前 `cn_etf_beta` 已经具备最小可交易能力，但现有规则仍停留在 `MA120 绝对过滤 + 60/120 日相对强弱 + 周频调仓` 的第一版骨架，收益与稳健性都不足以支持正式推进。现在需要把后续 ETF 研究收敛成少数几条成熟、可解释、可审计的规则族，避免继续在局部参数上低效试错。

## What Changes

- 新增一套针对 `cn_etf_beta` 的正式研究路线，限定为 3 组 ETF 规则族：
  - `Dual Momentum 基础版`
  - `Dual Momentum + 缓冲带`
  - `Dual Momentum + Vol Target`
- 为每组规则族定义：
  - 最小规则定义
  - 候选池范围
  - 防守 fallback 口径
  - 最小 AB 方案
  - 最小审计与验收口径
- 约束 ETF 研究优先级：
  - 优先研究 `510300 / 510050`
  - `511010` 仅作为防守 fallback
  - 暂不把 `510500 / 512100 / 512890` 作为本轮正式主候选
- 明确研究目标是比较规则族，而不是继续微调单个窗口参数。
- **BREAKING**：后续 `cn_etf_beta` 正式推进的默认研究入口，不再以“扩 ETF 候选池”为优先，而以规则族比较为优先。

## Capabilities

### New Capabilities
- `cn-etf-beta-rule-families`: 定义 A 股 ETF beta sleeve 的正式规则族研究框架、最小 AB 矩阵与研究边界。

### Modified Capabilities
- `cn-etf-beta-sleeve`: 明确当前 V1 规则只作为对照组，后续正式推进应基于规则族研究结果，而不是局部参数微调。
- `backtest-research-audit`: 为 ETF 规则族研究增加最小审计要求，确保 fallback、缓冲带、风险缩放都能在产物中被验证。
- `cn-a-portfolio-governor`: 明确 ETF 规则族研究与 Governor 的接口边界，尤其是防守 fallback 与 volatility target 如何映射到 sleeve 预算语义。

## Impact

- 影响 `openspec/specs/cn-etf-beta-sleeve`
- 影响 `openspec/specs/backtest-research-audit`
- 影响 `openspec/specs/cn-a-portfolio-governor`
- 后续实现预计会涉及：
  - `backend/core/engine_vector`
  - `backend/core/config`
  - `backend/core/audit`
  - `research/studies/etf`
