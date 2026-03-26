## Why

当前 `cn_etf_beta` 已经具备独立研究入口与最小可交易能力，但最近几轮研究已经证明：ETF 问题不只是参数细节，而是缺少一条明确服务于 “A 股 beta 层” 的宽基轮动模板。现在本地 ETF 目录已经足够支持一个 A0 直跑版，因此应该先把“宽基轮动模板 A”的研究边界、规则口径和最小 AB 方案正式固化，再决定是否推进为后续正式 ETF beta 路线。

## What Changes

- 新增一条正式的 ETF 研究模板：`宽基轮动模板 A`
  - 定义其服务对象是 A 股 beta 层，而不是行业轮动层或收益主引擎
  - 明确区分：
    - `A0`：当前可直接开跑版
    - `A1`：补齐标准中证1000 / 红利 ETF 后的目标正式版
- 固化模板 A 的最小规则骨架：
  - 月频主调仓
  - `12M / 6M / 3M` 相对强弱评分
  - `MA200 + 12M return > 0` 绝对过滤
  - `Top2` 等权持仓
  - `cash / 511010` 双 fallback 对照
- 固化模板 A 的最小 AB 设计：
  - 成长位：`159915` vs `588000`
  - 组合构建：`Top1` vs `Top2`
  - fallback：`cash` vs `511010`
  - 版本对照：`A0` vs `A1`
- **BREAKING**：后续宽基轮动研究必须显式区分“当前代理版”和“目标正式版”，不得把 `512100 / 512890` 静默伪装成标准中证1000 / 红利 ETF。

## Capabilities

### New Capabilities
- `cn-broad-based-etf-rotation-template-a`: 定义 A 股宽基轮动模板 A 的角色定位、A0/A1 版本边界、规则骨架与最小 AB 方案。

### Modified Capabilities
- `cn-etf-beta-sleeve`: 增加“宽基轮动模板 A”作为正式 ETF beta 研究族，并要求维持 beta core 语义而不是混入行业或防守角色。
- `cn-etf-research-entry`: 增加模板 A 的研究入口、A0/A1 预设与代理资产显式暴露要求。
- `backtest-research-audit`: 增加模板 A 的最小审计要求，证明评分、过滤、fallback 与 proxy 语义是否真实生效。

## Impact

- 影响 `openspec/specs/cn-etf-beta-sleeve`
- 影响 `openspec/specs/cn-etf-research-entry`
- 影响 `openspec/specs/backtest-research-audit`
- 后续实现预计会涉及：
  - `research/studies/etf`
  - `backend/core/engine_vector`
  - `backend/core/audit`
  - `outputs/ops/*` 的比较与总结产物
