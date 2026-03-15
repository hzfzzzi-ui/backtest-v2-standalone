## Context

当前仓库的主系统已经同时承载桌面研究平台、移动看板、实验运行、产物读取、执行预览和配置中心，但这些职责分布不清：

- [backtest_v2.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/api/endpoints/backtest_v2.py) 同时承担市场数据、公共校验、执行预览、manifest 读取和 artifact 读取。
- [_experiment_runner_api.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/api/endpoints/_experiment_runner_api.py) 同时承担请求模型、preset 解析、语义配置编译、同步运行、异步作业和配置快照。
- [backtest_v2_artifacts.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/api/endpoints/backtest_v2_artifacts.py) 既做 artifact 稳定化，也做 surface 拼装、CSV 衍生和实验索引回写。
- [backtest_v2.js](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/frontend/assets/js/backtest_v2.js)、[ui-controls.js](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/frontend/assets/js/ui-controls.js)、[artifacts.js](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/frontend/assets/js/artifacts.js) 共同承担页面壳、状态、配置草稿、API 调用、结果渲染和展示适配。
- 结果工作台已经有一条可用迁移缝：[results-workbench-bridge.js](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/frontend/assets/js/results-workbench-bridge.js) 和 [useResultsWorkbenchBridge.js](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/frontend/app/results-workbench/composables/useResultsWorkbenchBridge.js)，但目前仍被旧页面控制器直接牵制。

这会导致三个直接问题：

1. 桌面端、移动端和脚本入口没有共享稳定契约，字段含义和容错逻辑散落在多处。
2. 页面层、HTTP 路由层和应用编排层混在一起，任何一个功能改动都容易扩散到多个巨型文件。
3. 当我们准备把实验的机器读产物、人读结论和 baseline 报告并入主系统时，现有边界不够清晰，后续会继续膨胀。

## Goals

- 建立单一主系统边界：`Presentation -> Adapter -> Application -> Contract -> Engine/Service`。
- 把桌面端、移动端以及未来 CLI 命令面都收敛到同一套服务层和契约层，不再各自长独立逻辑。
- 为实验结果定义稳定契约，使桌面研究平台、移动看板、baseline 报告和未来脚本入口都围绕同一套 `manifest/surface/preview` 工作。
- 把前端页面壳、状态管理、API 客户端、feature 模块和展示转换拆开。
- 把后端 API 入口拆成聚合 router 和薄 route 文件，实质逻辑下沉到 services 与 contracts。
- 保持 baseline 可复现，避免在这次 change 里引入任何研究口径漂移。

## Non-Goals

- 本 change 不修改信号公式、不修改成交规则、不修改手续费和滑点。
- 本 change 不把桌面页面全部重写成新框架，也不要求把旧页面一次性迁空。
- 本 change 不直接处理回测主循环重写，那属于 `refactor-engine-execution-shell`。
- 本 change 不负责脚本治理本身，那属于 `refactor-script-surface`。
- 本 change 不落地统一 CLI、study runner 或 generated thin scripts；这里只把它们视为未来会消费同一套 contracts/services 的概念边界。
- 本 change 不展开新的移动审批写侧接口，移动端在本设计里只共享只读 contracts 和 services。

## Design Principles

### 原则 1：配置与结果都必须有唯一真相

- 配置真相由 `configDraft` 或持久化 config snapshot 表达。
- 实验结果真相由 `ExperimentManifest`、`ExperimentSurface`、`ExecutionPreview` 表达。
- 前端 presenter 只能消费契约对象，不再各自猜字段、补兼容和拼显示值。

### 原则 2：Presentation 不能直接决定研究语义

- 页面壳只做生命周期、事件装配和状态订阅。
- 研究配置编译、实验运行、结果读取、baseline 对比都必须下沉到后端 service。
- Vue 结果工作台只消费 snapshot，不主动 fetch 后端。

### 原则 3：Route 只做协议翻译，不做业务推导

- HTTP route 只负责：
  - 请求参数接收
  - 权限与输入检查
  - 调用 service
  - 把 service 结果序列化为 response
- route 文件中禁止继续增加 pandas 整形、artifact fallback 和 UI 兼容逻辑。

### 原则 4：兼容优先于漂亮

- 这次 change 的目标是划清边界，不是追求一次性最美结构。
- 兼容的是旧 HTTP path 和主要用户可见行为，不是旧文件结构本身。
- 所有旧入口都允许先降级为 shim，只要新边界能先立住；当前 `backend/api/endpoints/*` 最终可以删除。

## Target Architecture

```text
┌──────────────────────────────────────────────────────────┐
│                      Presentation                        │
├───────────────────────────────┬──────────────────────────┤
│ Desktop Research Page         │ Mobile Dashboard Page    │
│ index.html + page shell       │ mobile.html + page shell │
└───────────────┬───────────────┴──────────────┬───────────┘
                │                              │
                ▼                              ▼
┌──────────────────────────────────────────────────────────┐
│                    Adapter Surface                       │
├───────────────────────────────┬──────────────────────────┤
│ HTTP API                      │ CLI Commands             │
│ backend/api/...               │ future adapter surface   │
└───────────────┬───────────────┴──────────────┬───────────┘
                │                              │
                └───────────────┬──────────────┘
                                ▼
┌──────────────────────────────────────────────────────────┐
│                 Application / Use Cases                  │
├──────────────────────────────────────────────────────────┤
│ experiment_runtime_service                              │
│ experiment_artifact_service                             │
│ experiment_query_service                                │
│ experiment_compare_service                              │
│ experiment_summary_service                              │
│ baseline_report_service                                 │
│ mobile_dashboard_service                                │
└───────────────────────────────┬──────────────────────────┘
                                ▼
┌──────────────────────────────────────────────────────────┐
│                    Domain Contracts                      │
├──────────────────────────────────────────────────────────┤
│ ExperimentManifest                                      │
│ ExperimentSurface                                       │
│ ExecutionPreview                                        │
│ ResultsWorkbenchSnapshot                                │
│ ConfigSnapshot                                          │
└───────────────────────────────┬──────────────────────────┘
                                ▼
┌──────────────────────────────────────────────────────────┐
│                 Engine / Data / Artifacts               │
├──────────────────────────────────────────────────────────┤
│ stage_pipeline / engine_vector / portfolio              │
│ data access / runtime artifacts / execution outputs     │
└──────────────────────────────────────────────────────────┘
```

说明：

- 图中的 `CLI Commands` 只是整体系统边界中的概念位置，不是本 change 的主要交付。
- 本 change 的实际落地点是桌面端、移动端只读面和 HTTP API 边界。

## Directory and File Responsibilities

### Backend API

目标目录：

```text
backend/api/
  backtest_v2/
    router.py
    routes/
      market_data.py
      validation.py
      execution_preview.py
      experiments.py
      experiment_jobs.py
      artifacts.py
      configs.py
      history.py
    contracts/
      requests.py
      responses.py
      manifest.py
      surface.py
    adapters/
      request_adapter.py
      response_adapter.py
      http_errors.py
  mobile/
    router.py
    routes/
      auth.py
      dashboard.py
    contracts/
      requests.py
      responses.py
```

各文件职责：

- `backend/api/backtest_v2/router.py`
  - 只聚合子路由。
  - 不放任何 route 实现。
- `backend/api/backtest_v2/routes/market_data.py`
  - 行业、指数、个股行情、名称映射等只读接口。
  - 不读取 experiment outputs。
- `backend/api/backtest_v2/routes/validation.py`
  - 数据可用性和配置合法性检查。
  - 不触发正式回测。
- `backend/api/backtest_v2/routes/execution_preview.py`
  - 只返回执行预览契约。
  - 不产生正式实验结果目录。
- `backend/api/backtest_v2/routes/experiments.py`
  - 同步运行入口。
  - 只负责 `request -> service -> response`。
- `backend/api/backtest_v2/routes/experiment_jobs.py`
  - 异步作业提交、查询、取消。
  - 不包含实验运行细节。
- `backend/api/backtest_v2/routes/artifacts.py`
  - manifest / surface / artifact read / download。
  - 不自己写衍生 artifact。
- `backend/api/backtest_v2/routes/configs.py`
  - 配置中心和 config snapshots 相关接口。
- `backend/api/backtest_v2/routes/history.py`
  - 实验列表、过滤、分组摘要。
  - 默认返回 `manifest + 少量 perf 摘要`，不内联大 surface。
- `backend/api/backtest_v2/contracts/requests.py`
  - 所有 HTTP 请求模型。
- `backend/api/backtest_v2/contracts/responses.py`
  - 所有 HTTP 响应模型。
- `backend/api/backtest_v2/contracts/manifest.py`
  - `ExperimentManifest` 契约。
- `backend/api/backtest_v2/contracts/surface.py`
  - `ExperimentSurface` 和 `ExecutionPreview` 契约。
- `backend/api/backtest_v2/adapters/request_adapter.py`
  - 把 HTTP 请求对象转换成应用层输入。
- `backend/api/backtest_v2/adapters/response_adapter.py`
  - 把应用层对象序列化为前端稳定 response。
- `backend/api/mobile/router.py`
  - 聚合移动只读相关子路由。
- `backend/api/mobile/routes/auth.py`
  - 会话和认证相关接口。
- `backend/api/mobile/routes/dashboard.py`
  - 返回基于 `ExperimentSurface` 派生的移动摘要对象。

### Backend Services

目标目录：

```text
backend/core/services/
  experiment_runtime_service.py
  experiment_artifact_service.py
  experiment_query_service.py
  experiment_compare_service.py
  experiment_summary_service.py
  baseline_report_service.py
  audit_service.py
  data_ingest_service.py
  data_repair_service.py
  mobile_dashboard_service.py
```

职责定义：

- `experiment_runtime_service.py`
  - 唯一正式实验运行用例。
  - 吸收当前 `_experiment_runner_api.py` 中的运行编排逻辑。
- `experiment_artifact_service.py`
  - 负责产物稳定化、surface 组装前处理和 manifest 汇总。
- `experiment_query_service.py`
  - 负责实验索引、manifest 读取和已存在实验查询。
- `experiment_compare_service.py`
  - 对 baseline/champion/peer 进行对比。
- `experiment_summary_service.py`
  - 定义机器读 NAC、human summary 和实验结论对象的应用层输出契约。
  - 真正的批量输出流水线由 `refactor-script-surface` 落地。
- `baseline_report_service.py`
  - 定义 baseline ledger 和 baseline report 的应用层写入契约。
  - 真正的 baseline append 流水线由 `refactor-script-surface` 落地。
- `mobile_dashboard_service.py`
  - 只读移动端聚合。

### Frontend

目标目录：

```text
frontend/assets/js/
  pages/
    desktop_research_page.js
    mobile_dashboard_page.js
  state/
    workbench_state.js
    run_session_state.js
    active_experiment_state.js
    view_state.js
    mobile_state.js
  api/
    backtest_client.js
    mobile_client.js
  features/
    config_draft/
    run_control/
    execution_preview/
    artifact_surface/
    experiment_history/
    universe_picker/
  presenters/
    perf_presenter.js
    symbol_presenter.js
    funnel_presenter.js
    summary_presenter.js
  bridges/
    results_workbench_bridge.js
```

职责定义：

- `pages/*`
  - 页面 bootstrap、模块装配、URL 同步、生命周期。
- `state/*`
  - 切片化状态，不直接 fetch。
  - 最少拆成：
    - `configDraft`
    - `runSession`
    - `activeExperiment`
    - `viewState`
    - `mobileState`
- `api/*`
  - 统一 HTTP 调用。
  - 不做字段推导和 UI 拼接。
- `features/*`
  - 一块业务面板一个 feature。
- `presenters/*`
  - 纯显示适配层，把 contract 对象变成 UI model。
- `bridges/results_workbench_bridge.js`
  - 桌面壳和 Vue 工作台的唯一桥接边界。

### Results Workbench Boundary

结果工作台以后遵循这条单向关系：

```text
Desktop Page Shell
  -> fetch ExperimentSurface (+ lazy endpoints)
  -> build ResultsWorkbenchSnapshot
  -> bridge.setSnapshot(snapshot)
  -> Vue workbench renders only snapshot
```

硬约束：

- Vue workbench 不直接调用后端。
- 页面壳不直接操作 Vue 组件内部状态。
- snapshot 是唯一结果真相。
- 视图状态和研究配置分离，不能通过工作台桥修改运行配置。

## Domain Contracts

这次边界重构要确立三组核心契约。

### Contract 1: `ExperimentManifest`

用于描述实验身份、配置来源、运行元信息和 artifact 声明。

这是薄 manifest，不内嵌大段 perf/surface 数据。

最低字段：

- `exp_id`
- `baseline_id`
- `config_snapshot_ref`
- `runtime_route`
- `artifacts`
- `status`
- `created_at`
- `compare_refs`

### Contract 2: `ExperimentSurface`

用于桌面结果工作台、移动端摘要和 baseline 报告共享的结果面。

主 surface 最低字段：

- `summary`
- `perf`
- `audit`
- `machine_outputs`
- `human_outputs`

懒加载子面：

- `nav`
- `drawdown`
- `symbol_stats`
- `stage_funnel`

说明：

- 主 surface 默认承担 `summary / perf / audit`。
- 重内容通过子接口懒加载。
- 移动端不直接消费完整 `ExperimentSurface`，而是消费基于它派生的移动摘要对象。

### Contract 3: `ExecutionPreview`

用于研究平台执行预览、移动看板和未来执行侧摘要共享。

最低字段：

- `orders`
- `target_weights`
- `cash_usage`
- `risk_flags`
- `freshness`
- `as_of_date`

## Compatibility and Migration Strategy

### 阶段 0：冻结高风险入口

冻结以下文件，不再继续添加功能：

- [backtest_v2.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/api/endpoints/backtest_v2.py)
- [_experiment_runner_api.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/api/endpoints/_experiment_runner_api.py)
- [backtest_v2_artifacts.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/api/endpoints/backtest_v2_artifacts.py)
- [backtest_v2.js](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/frontend/assets/js/backtest_v2.js)
- [ui-controls.js](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/frontend/assets/js/ui-controls.js)
- [artifacts.js](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/frontend/assets/js/artifacts.js)

### 阶段 1：后端先拆 route 和 contracts

- 新增 `backend/api/backtest_v2/*` 目录。
- 新增 `backend/api/mobile/*` 目录。
- 把旧 endpoint 文件变成 router/shim。
- 先保持 path 不变，内部改成转调新 route/service。
- 新目录稳定后，删除旧 `backend/api/endpoints/*` 文件实现，只保留 path 兼容。

### 阶段 2：建立 services 和 contracts

- 先把 `_experiment_runner_api.py` 的编排逻辑搬进 services。
- 再把 `backtest_v2_artifacts.py` 的稳定化逻辑搬进 `experiment_artifact_service`。
- 最后补 `manifest / surface / preview` 响应契约。
- `experiment_summary_service` 和 `baseline_report_service` 在本阶段只固化契约与接口，不在本 change 内完成完整输出流水线。

### 阶段 3：前端页面壳与状态切片

- `backtest_v2.js` 先降级为页面壳。
- `ui-controls.js` 拆出配置草稿 feature 和 state。
- `artifacts.js` 拆出 presenter 和 artifact surface feature。
- 保持现有 DOM 结构尽量不动，先把逻辑搬走。

### 阶段 4：结果工作台正式边界化

- 用 `ResultsWorkbenchSnapshot` 收敛旧页面和 Vue 面板之间的数据交换。
- 桌面页壳只维护 snapshot，不再维护组件级字段。
- `nav / symbol_stats / stage_funnel` 通过子接口懒加载后再汇入 snapshot。

## Risks and Trade-offs

- 风险：同时迁移前后端边界，容易出现“双状态真相”。
  - 对策：所有 feature 迁移都以 contract 为中心，旧字段只读不写。
- 风险：route 拆分过程中响应 schema 漂移。
  - 对策：先固化 `manifest / surface / preview` 再拆 route。
- 风险：前端迁移后短期内存在旧 DOM 和新 state 并存。
  - 对策：允许 page shell 过渡期保留一层兼容适配，但不得继续扩张。
- 风险：服务层引入过多新文件，短期认知成本会上升。
  - 对策：每个 service 只承载一个 use case，不追求再建更复杂框架。

## Acceptance Criteria

- 桌面端、移动端，以及未来 CLI 命令面都围绕统一 services/contracts 设计；本 change 重点完成桌面端、移动端和 HTTP API 边界。
- `baseline_V10` 在相同输入下结果不漂移。
- 后端 API 入口文件只做装配和协议翻译，不再承载大段业务逻辑。
- 前端页面控制器只做 page shell 和模块装配，不再是“万能脚本”。
- `ResultsWorkbenchSnapshot` 成为结果工作台唯一输入真相。
- 所有新增机器读/人读结果引用都通过 `ExperimentSurface` 和 summary services 暴露。

## Open Questions

- 配置中心接口是否继续保留“按 URL source 切换”的兼容语义，还是一并规范为统一 config store。
- `ExperimentSurface` 的懒加载子接口是继续按 `nav / symbol_stats / stage_funnel` 三类拆分，还是后续合并其中部分只读面。
- 历史实验列表中的 perf 摘要最终固定到哪组字段，才能既满足加载弹窗对比，又不演化成第二套 mini-surface。
