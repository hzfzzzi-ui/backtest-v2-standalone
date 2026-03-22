## Context

当前仓库已经有一条可运行的每日同步链路，入口在 `backend/core/services/market_data_sync_service.py`。这条链路使用活交易日历推导 `target_trade_date`，并复用 `update_pams_ohlcv_daily` 把旧表补到目标日，再顺带刷新 `pit_index_daily`、`csi800 PIT` 与模拟盘自动同步。问题不在“没有自动更新”，而在于自动更新仍然围绕旧表 `pams_ohlcv_daily` 建立 freshness 语义。

与此同时，`baseline_V10.2` 主线已切到 `v2_canonical`，运行时正式依赖 `pams_ohlcv_daily_v2` 和 `pit_stock_moneyflow_v2`。因此，同步调度的成功判定与 freshness 状态如果仍锚定旧表，就会出现“旧表 fresh、主线 stale”的假新鲜。这个问题会污染桌面状态面、运维判断和后续研究纪律，属于正式主线口径错误。

这次变更只修正同步编排与 freshness 锚点，不扩展调度器职责，也不改前端契约。

## Goals / Non-Goals

**Goals:**

- 让 `cn_daily_sync` 在一次 run 内补齐 V2 主线所需的正式表。
- 明确正式顺序，避免先后依赖被打乱。
- 让 run record 的 `latest_trade_date_after` 与状态 API 的 `latest_*_trade_date` 代表 V2 主线 freshness。
- 保留旧表同步与 `pit_index_daily` 桥接，兼容现有依赖链。
- 保留结构化 run summary，便于核对 legacy/V2 各阶段结果。

**Non-Goals:**

- 不删除旧表链路，也不把所有消费者一次性切到 V2。
- 不重写各更新器内部逻辑，只复用现有 managed updater。
- 不修改 benchmark、regime、股票池或实验口径。
- 不新增前端字段或状态中心布局。

## Decisions

### 1. 继续保留旧表步骤，但 freshness 只认 V2 主线

决定：`update_pams_ohlcv_daily` 继续保留在调度最前面，但它只承担兼容桥接职责，不再作为主线 freshness 锚点。

原因：

- `pit_index_daily` 现有桥接依赖 `pams_ohlcv_daily` 的 `CN_INDEX` 数据，不宜在本次变更中拆掉。
- 仓库中仍可能有其他遗留消费者读取旧表，直接移除会扩大改动面。
- 用户问题的核心不是“旧表不该更新”，而是“旧表不该代表主线 freshness”。

备选方案：

- 直接删掉旧表同步：改动面更大，会影响 `pit_index_daily` 现有链路与遗留消费者，不符合最小改动。
- 保持旧表 freshness 语义不变：无法解决当前主线假新鲜问题，不能接受。

### 2. 将正式顺序固定为 legacy bridge -> V2 raw -> V2 canonical -> V2 moneyflow -> universe sidecar

决定：单次 `cn_daily_sync` 内按以下顺序执行：

1. `update_pams_ohlcv_daily`
2. `update_pit_index_daily`
3. `update_pams_ohlcv_daily_v2_raw`
4. `update_pams_ohlcv_daily_v2`
5. `update_pit_stock_moneyflow_v2`
6. `refresh_csi800_pit`
7. `sim_account_auto_sync`

原因：

- `pit_index_daily` 需要先吃到最新 `CN_INDEX` 兼容桥接结果。
- `pams_ohlcv_daily_v2` 依赖 raw staging，`pit_stock_moneyflow_v2` 又依赖 `pams_ohlcv_daily_v2` 已经生成 traded rows，这三步存在严格前后依赖。
- `csi800 PIT` 与 V2 日线不直接耦合，但在主线路径里属于 universe sidecar，放在 V2 主链之后更符合“先补市场数据，再补研究边界”的顺序。
- 模拟盘自动同步属于下游消费，必须最后执行，避免在主线数据未完成时继续向下游传播。

备选方案：

- 把 `csi800 PIT` 放在 V2 之前：技术上可行，但会把“主线市场数据补齐”与“股票池边界刷新”交错，不利于审计。
- 并行跑 V2 raw/main/moneyflow：当前服务层没有阶段隔离与部分失败恢复语义，且 main/moneyflow存在真实依赖，不适合这次最小改动。

### 3. 将 V2 freshness 定义为主表、moneyflow 侧表和 whitelist 的共同最小日期

决定：新增内部 helper，分别读取 `pams_ohlcv_daily_v2`、`pit_stock_moneyflow_v2`、`pit_stock_moneyflow_v2_whitelist_daily` 的最新交易日；V2 主线 freshness 取三者的共同最小值。若任一组件缺失，则 freshness 视为未知或落后。

原因：

- `pams_ohlcv_daily_v2` 只是主表；`moneyflow` 与 whitelist 仍是 V2 主线正式侧表。
- 如果主表到目标日而 moneyflow/whitelist 落后，研究层会继续拿到不完整的 V2 运行时依赖，不能对外宣称 fresh。
- 共同最小日期最容易审计，也最不容易制造假新鲜。

备选方案：

- 只看 `pams_ohlcv_daily_v2`：会忽略 moneyflow 与 whitelist 滞后，仍然可能误报 fresh。
- 将 `pit_index_daily` 也并入 DB fallback 最小日期：接口会把 benchmark 桥接和主线表混成一个锚点，语义不够清晰；`pit_index_daily` 失败仍由 run record 成功条件保证。

### 4. run summary 保留分阶段结果，run record 只写主线锚点

决定：`summary_json` 中保留 `legacy_daily_refresh`、`pit_index_daily_refresh`、`v2_raw_refresh`、`v2_main_refresh`、`v2_moneyflow_refresh`、`csi800_pit_refresh`、`sim_account_auto_sync` 等分阶段结果；但 `latest_trade_date_after` 与 skip/success 判定统一写 V2 主线锚点日期。

原因：

- 状态表只有单一 `latest_trade_date_after` 字段，必须明确其正式语义。
- 分阶段结果必须保留，否则出了问题只能看到“失败”，却不知道卡在 raw、main 还是 moneyflow。
- 这也是最小改动，不需要调整状态表 schema。

## Risks / Trade-offs

- [风险] V2 raw/main/moneyflow 任一步失败会让整次调度失败，失败率会高于旧链路
  处理：这是符合正式主线口径的显式失败，而不是回退到假新鲜；summary 中保留阶段结果用于人工补跑。

- [风险] V2 freshness 取共同最小日期后，状态可能比旧逻辑更“严格”
  处理：这是预期行为；主线只在完整补齐时才对外报告 fresh。

- [风险] 旧单测大量默认 `latest_trade_date_after` 来自 legacy summary
  处理：同步更新单测，让它们显式验证 V2 主线日期与阶段顺序。

- [风险] run summary 字段增多，后续消费者若假设 summary 结构固定可能受影响
  处理：保留原字段，同时新增分阶段字段，不移除现有 key。

## Migration Plan

1. 先更新 OpenSpec proposal/design/specs/tasks，固化 V2 主线同步合同。
2. 在 `market_data_sync_service.py` 中接入 V2 三段更新器与 V2 freshness helpers。
3. 调整 `run_cn_daily_sync_once()` 的 skip/success/failure 判定，使其基于 V2 主线日期。
4. 调整 `build_market_data_sync_status()` 的 DB fallback 口径，使其读取 V2 主线共同最小日期。
5. 补单测，覆盖：
   - 旧表已新但 V2 落后时不能 skipped
   - V2 主线成功时返回 success/fresh
   - moneyflow 落后时返回 failed/stale
6. 如需回退，只回退服务层改动即可；旧表更新器与状态表 schema 均无需变更。

## Open Questions

- 当前 `csi800 PIT` 是否需要在 run summary 中补一个显式的 `target_trade_date` 回显；这不阻塞本次实现，可留待后续增强。
