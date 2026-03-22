## Why

当前正式主线 `baseline_V10.1` 的正式锚点窗口是 `2016-2026`，而项目研究纪律同时要求保留更早窗口的正式可复现实验锚点。现在需要新增一条不改策略逻辑、只切换窗口与数据底座的正式 baseline，用于评估 `V10.1` 在 `2012-2016` 上、且基于 `V2 canonical + 严格历史 PIT` 的真实表现。

## What Changes

- 新增正式 baseline `baseline_V10.2`，其策略逻辑与 `baseline_V10.1` 保持一致。
- 将 `baseline_V10.2` 的研究窗口固定为 `2012-01-04 ~ 2016-12-30`。
- 将 `baseline_V10.2` 的数据角色切换为 `v2_canonical`。
- 将 `baseline_V10.2` 的股票池成员口径固定为 `HS300_ZZ500 + PIT_DYNAMIC`，并明确以严格历史成员解释该口径。
- 新增一条可复现的 baseline 注册与运行路径，用于生成实验结果并登记到 baseline 索引。

## Capabilities

### New Capabilities
- `baseline-anchor-registration`: 定义正式 baseline 版本锚点的配置、运行、登记和回退口径。

### Modified Capabilities
- `experiment-runtime-service`: 正式 baseline 注册流程需要允许以 `v2_canonical` 数据角色运行并落成可登记结果。

## Impact

- 影响代码：`backend/core/tools/baseline_access.py`、实验运行入口、必要的 ops 注册脚本。
- 影响产物：`outputs/baselines/baseline_V10_2/`、baseline 索引、正式 linked experiment。
- 不改动 `baseline_V10.1` 主逻辑，不改动现有执行壳与风控逻辑。
