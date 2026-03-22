## Context

当前 market data scheduler 已经负责 A 股日线刷新和 `csi800_pit` 刷新，但 market snapshot 读取指数基准时优先依赖 `pit_index_daily`，而该表没有被纳入每日调度，所以 `pams_ohlcv_daily` 已更新后，snapshot 仍可能看到过期指数日期。与此同时，模拟盘持仓快照已经有标准化与 reconcile 服务，但缺少日终自动导入器，也缺少把“外部持仓文件 -> 标准化快照 -> reconcile”串进 scheduler 的正式入口。

本次设计需要同时满足两个约束：
- 不改变 baseline 研究口径，只修复数据新鲜度与运行流水线。
- 不凭空发明新的外部券商依赖；在仓库内先用“外部导出 JSON 文件路径”作为自动导入边界。

## Goals / Non-Goals

**Goals:**
- 每日 A 股同步完成后，自动把最新 `CN_INDEX` 行情增量写入 `pit_index_daily`。
- 新增一个可配置的模拟盘持仓自动导入器，从 JSON 文件读取真实持仓并落标准化 snapshot。
- 导入成功后自动重跑 position-aware reconcile，并把最新结果暴露给 mobile/desktop 读取。
- 导入失败、文件缺失或日期落后时显式记录状态，不覆盖现有 `latest` 快照。

**Non-Goals:**
- 不接入新的券商 SDK、爬虫或网页登录自动化。
- 不改变策略信号、执行时点、资金分配或 mobile 主 schema。
- 不在前端重算 reconcile，也不把 `outputs/` 产物逻辑反向提升为业务源码。

## Decisions

### 1. `pit_index_daily` 继续沿用独立表，但接入每日 scheduler

决定：保留 `pit_index_daily` 作为 market snapshot 的基准指数真相源，不改成直接从 `pams_ohlcv_daily` fallback 读取；在 `run_cn_daily_sync_once()` 中于 `pams_ohlcv_daily` 更新成功后，同步调用 `update_pit_index_daily` 增量导入。

原因：
- 当前配置显式要求 `prefer_index_table=true` 且 `allow_cn_index_in_stocks_table=false`，直接改 provider fallback 会扩大影响面。
- 现有 `update_pit_index_daily.py` 已能做增量 upsert，复用成本最低。

备选方案：
- 方案 A：改 `pg_provider.load_benchmark_daily()` 在 `pit_index_daily` 落后时自动 fallback 到 `pams_ohlcv_daily`。  
  不采用：会改变运行时读数边界，属于更隐蔽的行为漂移。

### 2. 模拟盘自动同步采用“文件导入器 + 独立状态文件”

决定：新增 `sim_account_auto_sync_service`，从环境变量指定的 JSON 文件路径读取持仓；导入成功后调用 `store_holdings_snapshot()`，再调用 `run_position_aware_reconcile()`。同时在 `outputs/ops/sim_account/<account_id>/auto_sync_status.json` 记录最近一次自动同步状态。

原因：
- 仓库里当前没有稳定的真实模拟盘 API 接入层。
- 文件导入器边界清晰、可测试、可由外部任何脚本生成，不绑死单一提供方。

备选方案：
- 方案 A：直接把自动同步逻辑塞进 `sim_account_service.py`。  
  不采用：会把“标准化快照读写”和“外部导入运行态”混在一起。
- 方案 B：在 scheduler 里直接解析 JSON 文件。  
  不采用：职责过重，不利于测试和回退。

### 3. 自动 reconcile 使用市场同步目标日作为默认 `as_of_date`

决定：自动导入成功后，reconcile 默认使用本次 scheduler 的 `target_trade_date` 作为 `strategy_as_of_date`；若导入文件的 `trade_date` 晚于该日期，则拒绝本次 reconcile 并标记状态异常。

原因：
- 这样能保证“市场数据”和“策略观察日期”在同一日终闭环下对齐。
- 避免持仓日期超前于市场数据，导致不可靠的 action sheet。

### 4. 失败策略采用“保留旧 latest + 显式告警”

决定：无论 `pit_index_daily` 还是 sim-account auto sync，失败都必须显式落状态与 summary；但不会删除或覆盖旧的 `latest.json` / `reconcile/latest.json`。

原因：
- 用户宁可看到“旧但明确 stale”的结果，也不该被空白或半成品覆盖。

## Risks / Trade-offs

- [外部持仓文件缺失或格式错误] → 记录 `failed` 状态并保留旧快照，不覆盖 `latest.json`。
- [导入文件 trade_date 落后于市场目标日] → 标记 `stale_input`，允许保留旧 snapshot，但不生成新的 reconcile。
- [每日调度链变长] → 将 `pit_index_daily` 和 sim-account auto sync 都做成串行步骤并落 summary，便于定位到底卡在哪一段。
- [用户误以为自动导入等于真实成交回写] → 文档明确：该能力只同步“当前持仓真相”，不替代 execution event 写回。

