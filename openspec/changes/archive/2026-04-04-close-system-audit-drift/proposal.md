## Why

全系统审计表明，系统级重构主边界已经基本立住，但还没有真正进入“收口完成态”。当前最关键的阻塞不是数据库或主引擎，而是桌面端主工作流仍会向后端提交带有 `asset_context`、`unified_runtime` 等遗留字段的 `config_json`，导致 `加载配置 -> 改参数 -> 运行` 这一正式主工作流在前端直接失败。与此同时，数据库、前端和 cleanup 文档中仍有一批“实现已前进、文档仍停留在旧阶段”或“文档写成已完成、实现仍在 compat” 的漂移描述。

现在需要把这轮审计结果收成一条正式 change：一边修平桌面端运行合同，一边追平文档与实现现状，并把低频残留纳入正式审计闭环。否则系统会停留在“主边界看起来完成，但主工作流和文档真相仍不一致”的状态。

## What Changes

- 修复桌面端 `config_workspace -> run_orchestration` 提交链，确保提交给后端的 `config_json` 只包含 `FrontendSemanticConfig` 正式字段，剥离 `asset_context`、`unified_runtime`、遗留 `data_role` 等非正式字段。
- 明确新桌面壳在“主工作流可用”与“旧宿主完全退出”之间的当前状态，并追平相关前端架构文档。
- 更新数据库架构文档，明确事务域当前已经进入 DB 主读写 + compat 回退阶段，不再把 `outputs/mobile_ops/*`、`outputs/ops/sim_account/*` 描述为主要真相层。
- 把本轮审计发现的低频残留纳入正式 cleanup 规则，包括已删除旧文件后的 spec/test/comment 漂移，以及未再进入主读取面的 compat 结构。
- 新增一次“系统重构收口审计”能力，要求在大批量重构后，对文档漂移、主工作流和低频残留做统一复核。

## Capabilities

### New Capabilities
- `system-audit-closure`: 定义系统级重构后必须执行的统一审计，覆盖文档漂移、主工作流验证和低频残留扫描。

### Modified Capabilities
- `desktop-app-shell`: 桌面端正式运行链必须只向后端提交符合 `FrontendSemanticConfig` 的配置，不得透传遗留前端字段。
- `architecture-doc`: 系统与数据库/前端主文档必须追平当前实现阶段，明确哪些边界已正式完成，哪些仍处于 compat 过渡。
- `post-refactor-residual-cleanup`: cleanup 在删除残留前后都必须经过系统审计，并记录已删除对象对应的低频漂移是否已同步清理。

## Impact

- 前端桌面壳与配置/运行链：
  - `frontend/assets/js/state/config-draft-core.js`
  - `frontend/assets/js/desktop-shell/config-workspace.js`
  - `frontend/assets/js/desktop-shell/run-orchestration.js`
- 后端运行配置接口与 schema：
  - `backend/api/backtest_v2/semantic_config_schema.py`
  - `backend/api/backtest_v2/semantic_config_compiler.py`
- 主文档与 cleanup 文档：
  - `docs/02_系统架构设计/前端与移动端/*`
  - `docs/02_系统架构设计/数据库/*`
  - `openspec/specs/*`
  - `openspec/changes/cleanup-post-refactor-residual-files/*`
