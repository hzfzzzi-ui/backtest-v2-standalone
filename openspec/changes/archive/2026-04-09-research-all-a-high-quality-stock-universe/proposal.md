## Why

当前个股腿在 `2023-2026` 窗口内更像一条带明显 `CSI800` 大中盘 beta 背景的趋势增强腿。此前归因显示：

- 个股腿交易标的与 `CSI800` 窗口成分重叠约 `94.9%`
- ETF 腿在 `BULL / TRANS_DOWN` 下也主要承担股票类风险
- 两条腿的风险背景过近，削弱了组合分散

因此需要单独验证：如果只放开个股池到全市场，并用更高的数据/流动性门槛约束，个股腿是否会获得更高的 alpha 纯度或更好的窗口表现。

## What Changes

- 新增一条研究 change：只改个股腿股票池，不改信号、排序、退出、预算、ETF 和执行时点
- 运行两组 `cn_a_equity` stock-only 实验：
  - 基线：`HS300_ZZ500 + PIT_DYNAMIC`
  - 实验：`ALL_A + 高质量过滤`
- 记录窗口结果与风格重叠变化

## Capabilities

### New Capabilities
- `high-quality-all-a-stock-universe-research`: 研究全市场高质量股票池对个股腿收益与风格暴露的影响

### Modified Capabilities
- 无正式主线能力修改；本 change 仅产出研究结论

## Impact

- `openspec/changes/research-all-a-high-quality-stock-universe/*`
- 运行产物：`outputs/experiments/*`
