## Why

当前 ETF 研究仍然沿用“受 Governor 约束的辅助 beta sleeve”语义，导致宽基 ETF 的目标暴露、实际部署和进退逻辑都偏向保守配置层，无法匹配“独立 ETF 主线”应有的研究目标。现在需要把宽基 ETF 明确定义为受统一 CTA/Governor 管控、但拥有独立进入退出逻辑和独立暴露响应函数的正式主研究线，避免继续用个股 alpha 或辅助 sleeve 的语义研究 ETF。

## What Changes

- 新增“受统一 Governor 管控的独立宽基 ETF 轮动主线”能力，明确它不是行业 ETF 轮动、不是个股 alpha 的附属层，也不是不受约束的自由策略。
- **BREAKING** 重定义 `cn_etf_beta` 的正式语义：从“辅助 beta sleeve”调整为“独立宽基轮动主线”，研究目标、deployability 和暴露响应不再默认按个股 alpha 或旧 ETF stabilizer 语义解释。
- 为宽基 ETF 主线定义独立的进入/退出逻辑、state-aware target exposure、controlled accumulation 语义和 fallback 语义，但这些逻辑仍必须消费同一个 Governor/CTA 真相源。
- 明确限定本轮研究范围只包含宽基 ETF；行业 ETF、主题 ETF、个股 alpha 混合组合和 unified runtime 组合研究均不在本轮范围内。
- 扩展 research audit 与 ETF 研究入口，使实验能清楚回答“Governor 给了什么边界”“宽基 ETF 主线如何在该边界内自行决定进入、退出和承接便宜筹码”。

## Capabilities

### New Capabilities
- `cn-broad-based-etf-standalone-mainline`: 定义受统一 Governor 管控、但拥有独立进出与暴露策略的宽基 ETF 独立主研究线。

### Modified Capabilities
- `cn-etf-beta-sleeve`: 将 ETF 正式语义从辅助 sleeve 收口到独立宽基轮动主线，并限制当前范围只研究宽基 ETF。
- `cn-a-portfolio-governor`: 明确 Governor 对宽基 ETF 主线只输出统一状态真相和总风险边界，不再把 ETF 默认压成与个股 alpha 相同的风格暴露语义。
- `backtest-research-audit`: 要求 audit 显式解释 Governor 边界、宽基 ETF 主线自有进出逻辑、deployability 和承接式暴露决策。
- `cn-etf-research-entry`: 增加独立宽基 ETF 主线的研究入口与配置边界，禁止行业 ETF 在本轮研究中混入。

## Impact

- 影响后端 ETF 配置合同、Governor 与 ETF 的交互语义、ETF signal provider、research audit 和 ETF study 定义。
- 影响前端和结果产物中的 ETF 角色描述，但不要求本轮同步推进 unified runtime 或个股+ETF 组合入口。
- 不修改 A 股个股 baseline 主逻辑，不扩展行业 ETF 研究，不在本轮引入新的资产类别。
