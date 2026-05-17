## Why

`D7_DEEP_ONLY_IMMEDIATE_HALF_EXIT` 已完成三窗口证据闭环中的主窗口、硬门槛和全周期审计：

- `2016-01-01 ~ 2026-05-11` 主窗口：回撤与 Calmar 改善，且只增加有限 D5 半卖次数。
- `2012-07-12 ~ 2017-12-29` 硬门槛：同窗优于 B0 replay。
- `2012-07-12 ~ 2026-05-11` 全周期：D7 自身结果已完成，且裁齐到 `2026-05-08` 后仍保留真实 MaxDD / Calmar 改善。

用户已明确要求直接升格。当前正式 A 股 stock baseline `baseline_V10.1` 的 `linked_exp_id` 已丢失本地实验目录，且尚未吸收 D7 deep-only 规则，因此需要把正式锚点重挂到本轮 D7 全周期实验，并补齐可审计台账。

## What Changes

- **BREAKING**: `baseline_V10_1` 的正式 baseline truth 将从旧锚点重挂到 `exp_20260512_063520440_82bb`。
- `baseline_V10_1/config.json` 与 `baseline_config_snapshot.json` 将切换为 D7 deep-only 的全周期正式配置快照。
- `baseline_V10_1` 将补齐核心实验产物快照、promotion 说明和 baseline ledger/report。
- 不创建新的 stock baseline id；本次沿用 `baseline_V10_1`，以最小化前端默认加载、回归入口和引用路径的改动面。

## Capabilities

### Modified Capabilities

- `baseline-anchor-registration`: 允许在用户明确批准后，把 D7 deep-only 的全周期 stock-only 实验登记为 `baseline_V10_1` 的新正式锚点。
- `script-surface-governance`: 要求这次重挂同时写入 baseline ledger、report index、digest 和 latest champion。

## Impact

- 影响 `outputs/baselines/baseline_V10_1/` 下的 baseline 身份对象、配置快照和审计台账。
- 影响 `outputs/baselines/index.json` 中 `baseline_V10_1` 的 linked experiment 与摘要指标。
- 不修改 A 股 stock runtime 代码逻辑；只把已经通过研究审计的 D7 规则结果升格为正式 baseline truth。
- 不影响 `CN_STOCK_ETF_COMBO_BASELINE_V3` 的正式组合主线。
