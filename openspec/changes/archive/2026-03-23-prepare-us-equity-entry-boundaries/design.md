## Context

当前仓库已经有 `asset_scope`、`asset_context` 和 `multi-asset-entry-boundaries` 主 spec，但实现层仍存在三类隐式 A 股前提：

- 通用入口默认把未声明资产视为 `cn_a_equity`
- 通用服务名字看似多市场，实际实现只支持 A 股且无显式 adapter 边界
- 前端桌面壳和结果桥接层仍以 A 股文案、股票池和 fallback 作为默认语义

这会让“准备接入美股个股”的工作很容易退化成在 A 股主路径里追加 `if us_equity` 的补丁。本轮只做入口边界显式化，不接入真正的美股数据、交易日历或个股交易规则。

## Goals / Non-Goals

**Goals:**

- 让系统可以正式解析 `us_equity` 的 canonical asset scope，并把它稳定写入 asset context。
- 让 request contract、runtime compile、resolver、sync status 和前端壳显式消费资产上下文，不再依赖 A 股隐式默认。
- 保持当前 `cn_a_equity` 主线行为和 `baseline_V10.2` 运行口径不变。
- 对未实现的 `us_equity` 运行路径给出可审计的 unsupported error / status，而不是静默回退到 A 股。

**Non-Goals:**

- 不在本 change 中接入美股 security master、行情、复权、行业或 benchmark 数据。
- 不在本 change 中实现美股 universe resolver、market data sync adapter 或 execution rule。
- 不在本 change 中修改 A 股 baseline 主逻辑、执行时点或研究口径。
- 不在本 change 中移动大批 `cn_*` 数据构建目录。

## Decisions

### 决策 1：用注册表而不是 if-else 串联 asset profile

`asset_profiles.py` 改成显式 registry，当前注册 `cn_a_equity` 和 `us_equity`。这样 `resolve_asset_profile()` 可以稳定产出 canonical 上下文，后续新增资产时不会继续把 market/execution 规则散落到入口层。

不采用“先继续只有 A 股，等美股真接入时再重构”的方案，因为那会继续固化入口层的 A 股默认。

### 决策 2：通用入口去掉硬编码默认，但保留兼容解析链

request contract 与前端 payload 不再无条件写死 `cn_a_equity`。运行入口优先从 request / config_json / asset_context 解析 scope，只在兼容历史 baseline 或老 artifact 时通过 `build_asset_context()` 兜底到已知 canonical profile。

不采用“所有入口立刻强制 required asset_scope”的方案，因为当前已有大量 A 股 baseline、实验产物和测试仍依赖兼容解析。

### 决策 3：universe resolver 与 market sync 先做 adapter dispatch，再保留单一 A 股实现

`resolve_universe_by_mode()` 和 `build_market_data_sync_status()` 都先解析 canonical asset profile，再进入当前唯一的 A 股 adapter。`us_equity` 在这两条路径上明确返回 unsupported。

不直接实现美股 adapter，因为本轮目标是边界准备，不是资产接入落地。

### 决策 4：市场微观规则入口改成 profile-aware，但维持 A 股算法不变

`price_limits.py` 和 `audit_collector.py` 新增基于 `asset_scope / market_key` 的入口，当前只支持 `CN_A` 规则。对非 A 股调用立即失败，避免未来美股数据误复用涨跌停、tick size 等 A 股规则。

不在本轮抽象完整 market rules framework，只把最危险的全局默认收口。

### 决策 5：前端只做 asset-aware 壳，不做美股配置面板

桌面页标题、品牌、加载态和 `assetContext` fallback 改成 asset-aware。A 股专有控件和提示仍保留，但由 `asset_scope=cn_a_equity` 驱动；若 scope 为 `us_equity`，界面明确显示“入口准备中/未支持运行”。

不在本轮新增美股专用控件，避免半成品 UI 误导用户以为美股已可运行。

## Risks / Trade-offs

- [风险] 通用入口去掉 `cn_a_equity` 硬编码后，可能触发老 payload 的空 scope 路径变化 → 通过兼容解析链和回归测试锁住 A 股主线行为。
- [风险] 新增 `us_equity` canonical profile 后，部分模块可能以为系统已经支持美股运行 → 在 resolver、sync、market rules 入口统一返回 unsupported，避免假支持。
- [风险] 前端 asset-aware 壳改动可能影响已有文案和快照测试 → 仅调整 shell 文案与 fallback 逻辑，不改结果 workbench 协议。
- [风险] `asset_family` / `asset_class` 历史字段不一致 → 本轮在 asset context 中双写兼容，后续再单独收敛字段命名。

## Migration Plan

1. 新增 asset profile registry，保留 `cn_a_equity` 现有 profile，并加入 `us_equity` profile。
2. 调整 request contract、runtime compile、resolver 和 sync status 入口，使其显式传递并解析 asset scope。
3. 在 market rules 入口加入 explicit unsupported gate，防止非 A 股路径误用 A 股规则。
4. 调整前端桌面壳，使其从 `assetContext` 驱动品牌、标题和 fallback。
5. 运行针对入口层、sync status、frontend asset context 的回归测试。

回退策略：

- 回退本 change 即可恢复当前隐式 A 股入口行为。
- 不涉及数据库迁移。
- 若回归发现 `baseline_V10.2` 行为漂移，优先回退 request/runtime/fallback 相关改动，不需要回退现有 A 股数据主线。

## Open Questions

- `us_equity` 的 canonical benchmark / industry model 先使用占位值还是留空；本轮倾向于给稳定占位值，避免 context 结构再次变化。
- 市场同步状态接口未来是按 `asset_scope` 单接口复用，还是拆成多资产状态集合；本轮先保留单资产查询形态。
