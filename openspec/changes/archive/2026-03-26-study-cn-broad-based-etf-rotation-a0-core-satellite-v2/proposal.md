## Why

当前宽基轮动模板 A0 是现阶段唯一跑出可继续研究结果的 ETF 主线，但它仍然是“自由 Top2 轮动”形态，角色语义还不够清晰。现在需要把 A0 收敛成更接近正式 beta 层的“核心宽基槽位 + 成长卫星槽位”结构，并用最小单点替换验证 proxy 向标准 ETF 迁移是否成立。

## What Changes

- 新增 A0 V2 研究模板，将当前 A0 从“全池自由 Top2”改为“核心槽位 1 个 + 成长卫星槽位 1 个”的结构化宽基轮动。
- 固定 A0 V2 的对照基线为当前 A0 胜出版 `A0_GEM_TOP2_BOND` 的资产范围与月频动量骨架，不再同时引入新的大范围规则族。
- 新增最小 proxy 替换 AB，只允许：
  - `512100.SH -> 159845.SZ`
  - `512890.SH -> 510880.SH`
  的单点替换与全替换对照。
- 扩展 ETF beta sleeve 的研究语义，使其能够显式区分：
  - `core_slot`
  - `growth_slot`
  - `proxy_replacement_mode`
  - `slot_selection_reason_codes`
- 扩展 research audit，使 A0 V2 研究实验能明确回答：
  - 今天核心槽位选了谁
  - 成长槽位选了谁
  - 哪个标准 ETF 替换了哪个 proxy
  - 为什么某个槽位空缺或未部署

## Capabilities

### New Capabilities
- `cn-broad-based-etf-rotation-a0-core-satellite-v2`: 定义 A0 V2 的核心宽基槽位、成长卫星槽位、proxy 渐进替换 AB 和最小研究验收口径。

### Modified Capabilities
- `cn-etf-beta-sleeve`: 扩展 ETF beta sleeve 的研究语义，支持槽位化选择和 proxy 替换模式。
- `cn-etf-research-entry`: 扩展 A0/A1 之间的研究入口边界，允许 A0 V2 在受控范围内消费标准中证1000/红利 ETF 作为替换候选，而不是直接升格为 A1。
- `cn-a-portfolio-governor`: 扩展 Governor 对 ETF 槽位化目标暴露和 under-deploy 原因的审计语义。
- `backtest-research-audit`: 扩展 research audit，使其能统一暴露 A0 V2 的槽位选择、替换模式和未部署原因。

## Impact

- 影响代码路径：
  - `backend/core/engine_vector`
  - `backend/core/config`
  - `backend/core/audit`
  - `backend/api/backtest_v2`
  - `research/studies/etf`
- 影响实验产物：
  - `run_meta.json`
  - `audit.json`
  - `portfolio_daily.csv`
  - `outputs/ops/*`
- 不直接影响：
  - 个股 alpha 主线
  - unified runtime 入口
  - 前端结果协议主结构
