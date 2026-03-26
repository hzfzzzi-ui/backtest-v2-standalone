## Why

模板 A 的 A0 研究已经完成，并且标准中证1000 / 红利 ETF 已完成数据库接入。现在需要在标准资产池上重跑 A1 的最小对照，验证 A0 的结论在正式池上是否还能成立，并明确 A1 应使用的窗口与结论口径。

## What Changes

- 新增模板 A 的 A1 最小对照研究入口，基于标准中证1000 ETF `159845.SZ` 与标准红利 ETF `510880.SH`
- 固定 A1 最小对照窗口为 `2021-03-31 ~ 2026-03-25`
- 复用模板 A 已有规则骨架，只重跑三组最小对照：
  - 成长位：`159915` vs `588000`
  - 组合构建：`Top1` vs `Top2`
  - fallback：`cash` vs `511010`
- 输出 A1 compare/summary，并明确其与 A0 `2016-2026` 结果不可直接横向比较

## Capabilities

### New Capabilities
- `cn-broad-based-etf-rotation-template-a1-minimal-ab`: 定义模板 A 在标准中证1000 / 红利 ETF 接入后的 A1 最小对照研究要求与窗口口径

### Modified Capabilities

## Impact

- 影响 `research/studies/etf` 下的模板 A1 研究入口
- 影响 `outputs/ops` 下的 A1 compare/summary 产物
- 不影响当前 ETF provider 主逻辑
- 不影响当前 `first_wave_core/all` 正式预设
