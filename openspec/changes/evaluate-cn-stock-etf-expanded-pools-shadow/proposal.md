## Why

ETF-only 扩池结果已经显示行业主题与风格 Smart Beta 对 ETF sleeve 有改善，但这些结果尚未验证在正式 `stock + ETF` 组合语境下是否仍然成立。现在需要把 ETF 扩池放回 A 股个股 sleeve 旁边做联合影子实验，避免把单资产结论误读为组合层结论。

## What Changes

- 新增一组 research-only 的 `stock + ETF` 联合影子实验口径，固定 A 股个股 sleeve，只替换 ETF sleeve 候选池。
- 对比当前正式组合锚点、formal ETF rotation control、realworld、industry/theme、style/smart-beta 等 ETF 池在三窗口下的组合表现。
- 输出联合实验矩阵、exp_id、窗口、ETF 池、关键风险收益指标、交易/暴露信息和可归因结论。
- 明确该实验不迁移正式 ETF 池、不修改 `CN_STOCK_ETF_FORMAL_V1`、不修改股票 alpha、信号时点、成交时点、组合权重和防守层定义。

## Capabilities

### New Capabilities

- `cn-stock-etf-expanded-pool-shadow-evaluation`: 定义 A 股个股 sleeve 与扩展 ETF 池联合影子评估的实验合同、产物要求和防漂移约束。

### Modified Capabilities

- 无。

## Impact

- 影响范围：`openspec/changes/evaluate-cn-stock-etf-expanded-pools-shadow/`、`research/` 下的研究运行入口或辅助脚本、相关单测。
- 不影响范围：正式 baseline 注册、正式 ETF 池、A 股个股 alpha 逻辑、信号/成交时点、账户层、防守层核心定义、前端展示口径。
- 产物范围：运行结果写入 `outputs/`，仅作为研究产物和本轮报告证据，不作为源码主路径。
