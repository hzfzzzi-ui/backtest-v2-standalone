## Why

V9.1 baseline 当前在 `S4` 使用零缓冲的 45 日突破入场，容易把震荡区的轻微越过也当成有效突破。现有主链已经支持 `breakout_entry_buffer_pct`，但缺少一套受控、可复现、可审计的最小实验来验证小缓冲带是否能改善假突破噪声。

## What Changes

- 新增一套基于 `V9.1 baseline` 的突破缓冲带研究脚本，固定其余口径，只对 `strategy.params.breakout_entry_buffer_pct` 做对照实验。
- 输出实验摘要，明确记录 baseline 与轻量变体的核心绩效、交易数、持仓数和结果目录。
- 在实验脚本中加入口径审计，确保股票池、成本、执行方式、退出规则和基准配置不发生漂移。

## Capabilities

### New Capabilities
- `breakout-buffer-experiment`: 以 V9.1 baseline 为锚点，运行并归档仅改变突破缓冲带的最小可证伪实验。

### Modified Capabilities

无。

## Impact

- 影响代码：`backend/scripts/` 下新增研究脚本。
- 影响系统：实验运行器、结果产物目录、研究归档说明。
- 不影响：策略主链逻辑、baseline 默认配置、前后端配置协议。
