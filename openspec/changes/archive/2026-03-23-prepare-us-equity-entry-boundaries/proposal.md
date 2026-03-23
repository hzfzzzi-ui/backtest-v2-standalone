## Why

当前系统虽然已经引入了 `asset_scope` 和 `asset_context`，但主入口、通用服务和前端壳子仍把 A 股当作隐式全局默认。继续在这种状态下接入美股个股，会把 `CN_A` 规则、交易时点、股票池语义和同步口径继续污染到通用层，后续很难审计和回滚。

## What Changes

- 引入显式 `asset profile` 注册表，允许系统正式解析 `cn_a_equity` 与 `us_equity` 两类 canonical asset scope，但当前只落地 A 股 adapter。
- 调整通用运行入口，不再在 request contract、runtime compile 和前端 payload 中无条件写死 `cn_a_equity`，改为显式透传或从已有配置/manifest 解析。
- 将 universe resolver 改为“先按 asset profile 分发，再进入 A 股 resolver”的结构；未支持资产必须显式报错。
- 将 market data sync / freshness status 改为显式消费 `asset_scope`，当前只支持 `cn_a_equity`，但不得继续把 A 股同步口径伪装成全市场默认。
- 将前端桌面壳改成 asset-aware：品牌文案、资产上下文、A 股专有提示和 universe 控件都由 `asset_scope` 驱动，而不是全局默认 A 股。
- 将引擎中的市场微观规则入口显式绑定到 market profile；当前仍只实现 A 股规则，但未支持资产必须显式失败。

## Capabilities

### New Capabilities

- 无

### Modified Capabilities

- `multi-asset-entry-boundaries`: 收紧 canonical asset scope / asset profile / market profile 的入口边界，并允许 `us_equity` 作为正式可解析 scope 出现在运行上下文中。
- `universe-resolver`: 要求 resolver 按 asset profile 分发，并对未实现资产返回显式 unsupported。
- `cn-daily-data-sync`: 要求同步服务显式声明 `cn_a_equity` adapter，而不是继续把 A 股同步器当成隐式全市场服务。
- `market-data-freshness-status`: 要求 freshness status 显式携带 `asset_scope` 并对未实现同步资产给出 unsupported 状态。
- `results-workbench-snapshot-boundary`: 要求桌面结果壳和 snapshot 消费链改为 asset-aware，不再从 A 股默认文案或字段回推资产语义。

## Impact

- 后端入口：`backend/core/config/asset_profiles.py`、`backend/api/backtest_v2/contracts/requests.py`、`backend/api/backtest_v2/runner_impl.py`、`backend/core/services/experiment_runtime_service.py`
- universe / runtime：`backend/core/universe/universe_resolver.py`、`backend/core/tools/runtime_data_access.py`
- 市场同步 / freshness：`backend/core/services/market_data_sync_service.py`、`backend/api/backtest_v2/data_impl.py`
- 市场规则：`backend/core/engine_vector/audit_collector.py`、`backend/core/data/price_limits.py`
- 前端壳与状态：`frontend/index.html`、`frontend/assets/js/backtest_v2.js`、`frontend/assets/js/artifacts.js`、`frontend/assets/js/pages/*.js`、`frontend/assets/js/state/config-draft-core.js`
- 测试：对应 unit / frontend / integration 回归测试
