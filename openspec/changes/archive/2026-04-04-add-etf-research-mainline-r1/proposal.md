## Why

当前 ETF 研究线虽然已经有 standalone mainline 与 governed exposure 的探索模板，但还缺一条明确面向“独立收益主线”的 research-only 版本：它需要把 A 股宽基作为主收益来源、把黄金和债券收口为防守层、把成长席位固定到 `588000.SH`，并显式允许双周节奏与弱市小幅承接。现在补这条主线，是为了先建立一条可复现、可审计、可回测归因的 ETF 研究基线，再决定后续是否值得推广。

## What Changes

- 新增一条 `research-only` 的 ETF 独立收益主线 study：`etf/cn_broad_based_research_mainline_r1`
- 该 study 使用新版 ETF 单腿架构，采用 `governed_broad_based_standalone_mainline` 角色，不修改 formal ETF sleeve 真相
- 策略池收口为 A 股核心承接 + 固定科创成长席位 + 黄金/债券双防守
- 调仓频率改为 `biweekly`，选择链使用 `core_growth_slot`
- 弱市允许 `LIGHT / TRANS_DOWN / RISK_OFF` 继续小幅承接 A 股核心宽基，但 `RISK_OFF` 不放出成长席位
- 新增对应 generated thin script 与最小 study contract 测试，确保配置链和研究入口可回归

## Capabilities

### New Capabilities
- `cn-etf-research-mainline`: 定义一条 research-only 的 ETF 独立收益主线能力，支持双周调仓、固定科创成长席位、黄金/债券双防守，以及弱市核心宽基小幅承接

### Modified Capabilities
- `cn-etf-research-entry`: 增加一条新的 ETF research study preset，要求受控研究入口能够装载并运行该主线

## Impact

- 受影响代码：
  - `research/studies/etf/`
  - `backend/scripts/generated/`
  - `tests/unit/`
- 受影响系统：
  - ETF 研究入口
  - study_runner 执行计划
  - ETF 单腿 research-only 回测主线
- 不在本次范围：
  - formal `cn-etf-beta-sleeve` 合同
  - stock+ETF combo
  - 前端与结果页结构
