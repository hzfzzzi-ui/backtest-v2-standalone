## Context

当前仓库已经具备 A 股日线写库能力，入口是 `backend/cli/managed/update_pams_ohlcv_daily.py`，并且该实现已经支持按目标结束日补齐到 `pams_ohlcv_daily`。但它仍是人工触发链路，没有正式调度器、没有同步运行状态真相源，也没有面向桌面端的轻量 freshness 状态接口。

当前部署形态是单个 `backtest-v2-standalone` 容器，`backend/main.py` 没有后台 scheduler，也没有额外 worker/cron 服务。桌面端已有状态中心与 `backtest_v2` 主 HTTP 路由，但没有“最新同步日期”的正式状态面。这个变更需要同时跨越数据落库、运行调度、API 边界和前端状态展示，因此需要先明确技术边界，避免实现阶段出现“再写一套抓数逻辑”或“前端自己猜数据库日期”的漂移。

## Goals / Non-Goals

**Goals:**
- 让 A 股系统每天按固定时间自动把 `pams_ohlcv_daily` 补到前一交易日。
- 复用现有 `update_pams_ohlcv_daily` 落库逻辑，避免形成第二套抓数/写库真相源。
- 为每次同步保留可审计状态，包括目标交易日、成功/失败、时间戳、摘要和错误信息。
- 通过正式 API 向桌面前端暴露“最新同步日期”和 freshness 状态，并在 A 股系统中显性展示。
- 不改变回测主逻辑、执行时点、研究口径和实验产物语义。

**Non-Goals:**
- 不在本次变更中扩展到美股、加密或多市场统一调度器。
- 不做盘中分钟级同步，也不做实时行情订阅。
- 不在前端提供手工补历史全量数据的复杂运维面板。
- 不把同步状态耦合进实验 `surface`，避免系统状态和单次实验结果混在一起。

## Decisions

### 1. 调度器内嵌到现有 backend 服务，并通过环境变量控制

系统采用“FastAPI 启动时拉起后台同步循环”的方式，而不是新增独立 cron 容器。原因是当前部署只有一个 `backtest-v2-standalone` 服务，新增独立 worker 会引入额外的 compose 角色、日志面和运维复杂度；而内嵌调度器能够最小化部署改动，并保持“用户打开系统就有日更能力”的直觉。

调度器必须满足：
- 默认在 `Asia/Shanghai` 时区工作。
- 默认每天固定时间触发一次，时间通过环境变量配置，且 compose 中提供默认值。
- 调度失败不会阻断 HTTP 服务启动；它只能影响同步状态，不得拖垮研究台主路径。
- 需要单进程内互斥，且推荐使用数据库 advisory lock 防止未来多实例部署时重复执行。

备选方案：
- 独立 cron / sidecar：更解耦，但当前项目没有现成调度服务基础，落地成本更高。
- 系统外部 Windows Task Scheduler：与仓库内行为脱节，不满足“系统内正式能力”的要求。

### 2. 目标日期按“前一交易日”计算，真相源来自活交易日历源

同步目标不能简单使用自然日 `today - 1`，因为周末和节假日会错误触发。系统必须以交易日历为真相源，计算“当前时点之前最近一个已开市 A 股交易日”作为 target trade date。当前正式来源是活交易日历 API，而不是数据库中的旧 `pit_trade_cal` 或前端猜测。

当前实现中，target trade date 应优先来自活数据源，具体为 Tushare `trade_cal`。原因是当前库中的 `pit_trade_cal` 已被确认可能停更，不能再作为日更同步目标的正式真相源。`pit_trade_cal` 可以保留给历史审计或旧逻辑，但 scheduler 和 freshness 状态聚合不再依赖它。

如果活交易日历缺失或不可读：
- 同步器不得盲目退化成自然日同步。
- 本次运行应标记为 `failed` 或 `unknown`，并把错误写入同步状态真相源。

备选方案：
- 使用自然日前一天：实现简单，但会在非交易日制造错误或空跑，破坏可信性。
- 从 `pams_ohlcv_daily` 自推最新日再加一：对追平逻辑有帮助，但不能替代 target date 的正式判定。
- 继续依赖 `pit_trade_cal`：当前真实环境已证明它可能与活行情表失步，会把同步目标静默拉回旧日期，不再可接受。

### 3. 复用现有 `update_pams_ohlcv_daily`，同步器只负责编排，不重新实现抓数

调度器必须复用现有 `backend/cli/managed/update_pams_ohlcv_daily.py` 的核心能力，以 `apply=true` 方式执行到目标日期。必要时可以把其中的“构造参数 + 调用 run_update”抽成可复用服务，但不允许再写一套独立抓数逻辑。

这样做的理由：
- 现有 CLI 已经具备 `latest_cn_a_before/after` 等摘要字段，可以直接用于同步状态。
- 现有 upsert 逻辑已经是 `pams_ohlcv_daily` 的正式写入真相源，重复实现只会产生 drift。
- 同步器只需要决定“何时跑、跑到哪天、如何记状态”，不应该接管底层抓数细节。

### 4. 使用独立的同步运行状态表作为真相源

系统新增独立的同步运行状态表，建议命名为 `pams_data_sync_runs`。每次调度尝试都写入一条记录，至少包含：
- `sync_key`
- `asset_scope`
- `target_trade_date`
- `status`
- `started_at`
- `finished_at`
- `latest_trade_date_before`
- `latest_trade_date_after`
- `rows_upserted`
- `summary_json`
- `error_text`

前端展示和 API 返回应以该表加数据库实际最新日期组合而成的服务对象为准，而不是前端直接执行 `MAX(trade_date)`。这样可以同时表达：
- 最新成功同步到哪一天
- 最新一次运行是成功、失败、运行中还是禁用
- 当前是否落后于 target trade date

不单独维护第二张“current status”表，避免双写。当前状态由最近一次运行记录和最近一次成功记录派生。

### 5. 暴露薄 `sync_status` API，而不是把 freshness 塞进实验 surface

系统新增一个独立的市场数据状态接口，建议路径为 `/api/backtest_v2/market_data/sync_status`，归属现有 `market_data_router`。该接口返回桌面前端所需的最小状态对象，例如：
- `asset_scope`
- `dataset_key`
- `scheduler_enabled`
- `status`
- `latest_success_trade_date`
- `latest_available_trade_date`
- `target_trade_date`
- `lag_days`
- `last_run_started_at`
- `last_run_finished_at`
- `last_run_status`
- `message`

不把这类系统 freshness 放进单个实验 `surface`，原因是：
- 同步状态是系统级而不是实验级信息。
- 实验结果页未必被加载，但用户仍然需要知道当前数据库新鲜度。
- 把系统状态塞进 `surface` 会污染结果工作台的职责边界。

### 6. 前端在命令栏显性展示最新同步日期，并在状态中心展示详情

桌面前端需要两个展示层：
- 命令栏或等价顶层状态位：始终显性展示“最新同步日期”，例如 `数据同步：2026-03-15`
- 状态中心：展示同步状态、目标交易日、最近一次错误或 lag 描述

展示语义必须区分：
- `fresh`
- `stale`
- `running`
- `failed`
- `never_synced`
- `disabled`

前端不得把缺失日期渲染成 `0`、空字符串拼接产物或自行拼装错误状态；它只消费 API 返回的正式字段。

## Risks / Trade-offs

- [风险] 调度器内嵌到 Web 进程后，异常处理不当可能拖慢或污染主服务日志
  → Mitigation：后台线程独立捕获异常、写同步状态、绝不让异常冒泡阻断 FastAPI 请求线程。

- [风险] 单实例假设未来可能失效，多实例部署下可能重复跑同步
  → Mitigation：增加进程内互斥和数据库 advisory lock，确保同一 `sync_key` 同时最多只有一个执行者。

- [风险] 活交易日历源缺失或临时异常会导致 target trade date 无法判定
  → Mitigation：显式标记 `unknown/failed`，不允许静默退化为自然日；并把失败状态写回 `pams_data_sync_runs`。

- [风险] 状态接口和 scheduler 都读取活交易日历源，可能产生额外外部依赖
  → Mitigation：当前场景是个人单实例系统，请求量低，可接受；若后续频率提升，再引入缓存或专用 calendar snapshot。

- [风险] provider 在配置时间点尚未出完整日线，可能导致当天第一次同步失败
  → Mitigation：同步器按固定频率检查是否需要追平，失败保留状态并允许下一次 tick 重试；同步时间通过环境变量可调。

- [风险] 新增同步状态表属于 schema 扩展，当前仓库没有完整 migration 框架
  → Mitigation：本次变更使用明确的建表 helper 或初始化步骤，并提供回退开关；实现时附上 DDL 与验证查询。

- [风险] 前端若在系统未同步成功前渲染日期，用户可能误解为“接口坏了”
  → Mitigation：前端必须把 `never_synced` / `failed` / `disabled` 显式显示为状态文案，而不是空白。

## Migration Plan

1. 新增同步状态表与读取服务，不改变现有人工 CLI 行为。
2. 在 backend 中引入后台 scheduler，但通过环境变量控制启停；compose 默认开启，便于 standalone 场景直接可用。
3. 新增 `/api/backtest_v2/market_data/sync_status` 接口，并先在前端只读展示，不影响实验加载链路。
4. 部署后通过数据库和 API 校验最新成功同步日期、最新运行状态和前端显示是否一致。
5. 如需回退，先将 `CN_DAILY_SYNC_ENABLED=false` 停掉后台调度，再回退前端状态展示和 API；同步状态表可以保留，不影响现有回测链路。

## Open Questions

- 默认触发时间暂定为收盘后晚间时段，并允许通过环境变量覆盖；实现前只需确认 compose 默认值即可，不构成架构阻塞。
