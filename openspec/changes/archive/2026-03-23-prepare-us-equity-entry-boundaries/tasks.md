## 1. OpenSpec 与入口边界

- [x] 1.1 补齐 `multi-asset-entry-boundaries / universe-resolver / cn-daily-data-sync / market-data-freshness-status / results-workbench-snapshot-boundary` 的 delta spec，并明确 `us_equity` 只可解析不可运行。DoD：spec 可被 `openspec validate --strict` 通过；验证：OpenSpec 校验；风险：spec 若写得过宽会误承诺美股已可运行。
- [x] 1.2 将 asset profile 入口改为 registry 结构，支持 `cn_a_equity` 与 `us_equity` canonical scope，并在 asset context 中补齐 `asset_family` 兼容字段。DoD：`build_asset_context()` 可产出两类 canonical profile；验证：`tests/unit/test_asset_profiles.py`；风险：老 artifact 对 `asset_class` 字段仍有依赖。

## 2. 通用入口与通用服务

- [x] 2.1 收紧 API request / runtime compile / runtime data access 的 `asset_scope` 传递链，移除通用入口中的硬编码 `cn_a_equity` 默认。DoD：request contract、runner、runtime compile、validation access 都显式消费 asset scope；验证：相关 unit tests；风险：历史空 payload 兼容性。
- [x] 2.2 将 universe resolver 改成按 asset profile 分发，当前仅保留 A 股 adapter，其他 asset scope 显式 unsupported。DoD：`resolve_universe_by_mode()` 对 `us_equity` 返回可审计错误；验证：resolver/runtime data access 单测；风险：动态股票池元数据回填缺失。
- [x] 2.3 将 market data sync / freshness status 改成显式 asset-aware 状态接口，当前只支持 `cn_a_equity` adapter。DoD：状态 payload 含 `asset_scope`，`us_equity` 返回 unsupported；验证：`tests/unit/test_market_data_sync_service.py` 与 API 相关测试；风险：旧前端读取无 query 参数的兼容性。
- [x] 2.4 将 price limit / audit collector 的市场规则入口显式绑定到 `asset_scope` 或 `market_key`，禁止非 A 股路径静默复用 A 股规则。DoD：非 A 股调用显式失败，A 股行为不变；验证：新增/更新 unit tests；风险：引擎内部调用点遗漏。

## 3. 前端 asset-aware 壳与回归

- [x] 3.1 将桌面前端壳改成 asset-aware：品牌标题、snapshot fallback、loaded source 与运行 payload 都从 asset context 驱动，而不是写死 A 股默认。DoD：前端不再用 `cn_a_equity` 作为通用 fallback；验证：`tests/unit/test_frontend_runtime_boundaries.py`、`tests/frontend/test_multi_alpha_workbench.cjs`；风险：旧壳文案和加载流回归。
- [x] 3.2 对 A 股专有 universe/提示文案加显式 scope 约束，并为 `us_equity` 显示“入口准备中/未支持运行”的壳层状态。DoD：当前 A 股界面不变，切到 `us_equity` 时不会伪装成 A 股；验证：前端源码断言与手工 smoke；风险：UI 上出现半支持状态误导用户。
- [x] 3.3 跑最小回归集并记录回退面。DoD：核心 unit/frontend tests 通过并能说明未改动 A 股 baseline 口径；验证：pytest/npm 相关命令；风险：历史无关测试噪音掩盖真实回归。
