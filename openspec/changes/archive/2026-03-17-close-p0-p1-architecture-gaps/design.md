## Context

当前仓库已经形成以 `backend/main.py -> api/backtest_v2 -> core.services/core.tools -> foundation_shell/stage_pipeline -> outputs` 为主链的 A 股研究平台骨架，但仍存在四类会直接放大后续 change 风险的结构问题：

1. 默认测试集无法稳定 collect，脚本迁移后的正式入口与测试依赖面不一致。
2. CLI、脚本和前端页面仍保留双轨或混合 owner，导致“正式入口”与“实际活跃入口”并不完全一致。
3. `backend/api/backtest_v2` 继续承担较多编排、编译和产物组织职责，边界层与应用层分离不彻底。
4. 架构守则、协议文档和仓库现实未完全对齐，导致 change 评审标准与代码现状之间存在缝隙。

本 change 的约束非常明确：只做 `P0/P1` 收口，不改 `baseline_V10.1` 的研究口径，不把新资产接入、前端重写和策略逻辑优化绑进同一轮。

## Goals / Non-Goals

**Goals:**

- 以 `P0 -> P1` 两个波次收口当前最影响后续开发安全性的架构债务。
- 让默认 `pytest` 测试集至少完成稳定 collect，并让关键治理测试与主线回归门重新可信。
- 将正式入口收口到 `backend/cli`、`backend/cli/managed` 和 `backend/scripts/generated`，停止让历史脚本导入面继续扮演隐式正式接口。
- 明确桌面前端的 owner 模型：旧壳负责 bootstrap 和编排，配置核心与结果工作台分别由独立模块承载。
- 继续降低 `backend/api/backtest_v2` 的混合职责，把可下沉的编排和真相构建逻辑收回 `core.services` / `core.tools`。
- 补齐当前目录树、协议文档、示例与 change 守门标准，使文档和仓库现实重新对齐。

**Non-Goals:**

- 不重写桌面前端为全 Vue 架构。
- 不改变 `baseline_V10.1` 的信号时点、执行时点、成交规则、股票池和防守层定义。
- 不在本轮中正式接入美股 ETF、加密现货或新的 market adapter。
- 不做无关的 UI 美化、收益优化或大规模 opportunistic refactor。

## Decisions

### 决策 1：采用双波次收口，而不是一次性大清理

- 选择：将工作拆为 `P0` 和 `P1` 两个波次，先修默认测试、正式入口和前端 owner，再处理 API 分层、文档补齐和进一步瘦身。
- 原因：当前问题横跨测试、脚本、前端和 API；一次性并行推进会重新制造不可归因的大改动。
- 备选方案：
  - 单轮全量清理：拒绝。风险过高，且不符合当前仓库的最小改动纪律。
  - 只修测试不修边界：拒绝。会让通过的测试继续覆盖错误的正式入口。

### 决策 2：把“默认 pytest collect 成功”设为 P0 硬门

- 选择：本轮将默认 `pytest` collect 成功视为最基础的 P0 通过条件。
- 原因：当前测试在收集阶段就失败，说明正式脚本面和测试依赖面已经失配；若不先修，后续任何 change 的回归门都不可靠。
- 备选方案：
  - 仅要求关键治理测试通过：不足。因为默认测试面本身已经失真。
  - 暂时跳过失败测试：拒绝。会掩盖入口迁移未完成的问题。

### 决策 3：正式入口只保留单一主语义

- 选择：正式命令面以 `backend/cli` 为中心，`backend/cli/managed` 承载复用命令实现，`backend/scripts/generated` 只保留薄脚本入口；`backend/core/cli` 仅允许作为短期兼容壳或退场对象。
- 原因：当前入口双轨是认知漂移和测试漂移的根源之一。
- 备选方案：
  - 长期保留 `backend/core/cli` 与 `backend/cli` 双入口：拒绝。
  - 完全删除所有顶层脚本：暂不采用。generated thin script 仍是研究入口的实用载体。

### 决策 4：前端维持混合架构，但必须冻结 owner 边界

- 选择：不在本轮全量 Vue 化，而是明确旧桌面壳只负责 bootstrap、控件编排和桥接；结果区由 Vue workbench 单 owner；配置草稿和 runtime request 由独立核心模块承载。
- 原因：完全前端重写超出本轮范围，但继续允许旧壳吸收新逻辑会让债务反弹。
- 备选方案：
  - 直接全量迁移到 Vue：成本高、与本轮目标不匹配。
  - 继续保持混沌共存：拒绝，会继续放大后续 change 风险。

### 决策 5：API 包只保留边界职责，应用编排尽量下沉

- 选择：`backend/api/backtest_v2` 继续承担 contracts/routes/public request validation，但把可复用的运行时编排、真相构建和协议稳定化逻辑尽量收回 `core.services` 与 `core.tools`。
- 原因：API 边界层继续膨胀会让“公共协议”与“应用实现”再次耦合。
- 备选方案：
  - 在 API 包内部继续横向拆文件：只解决体积，不解决职责归属。
  - 一次性大搬家到全新 service 层：风险偏高，本轮不采用。

### 决策 6：文档同步属于本轮交付，不做后置补票

- 选择：将 `ARCHITECTURE`/schema/example/runbook 级文档补齐纳入 P1 正式交付。
- 原因：当前 change 的核心就是“收口”，若文档仍滞后，change 结束后守门规则依旧失真。
- 备选方案：
  - 实现后再补文档：拒绝，会重复当前问题。

## Risks / Trade-offs

- [跨模块改动范围大] → 通过 `P0/P1` 双波次和每波显式通过条件控制范围，禁止把多资产接入和策略逻辑改动混入本轮。
- [测试修复可能演化成“改测试配现实”] → 每个测试修复都必须以正式入口定义和主线回归结果为锚，不允许单纯删除失败测试。
- [API 下沉可能引发调用链抖动] → 仅迁移边界外的应用编排与真相构建，保持 public route、request contract 和 artifact protocol 不变。
- [前端 owner 收口可能短期保留桥接重复] → 允许短期桥接存在，但禁止双 owner 继续写同一块可见结果 DOM。
- [文档补齐容易变成空文档] → 文档必须绑定代码路径、运行命令和产物协议，而不是写成抽象架构描述。

## Migration Plan

1. `P0-基线冻结`：确认 `baseline_V10.1` 当前回归快照、保留现有 smoke/default pytest 配置，并记录必须不漂移的验证命令。
2. `P0-测试与脚本收口`：修复默认测试 collect 失败，统一测试对正式脚本面的依赖，更新 inventory 与 governance 断言。
3. `P0-入口与前端 owner 收口`：明确官方 CLI/managed/generated surface，冻结旧桌面壳职责，补 owner 边界测试。
4. `P0-验收`：默认 `pytest` collect 成功，关键治理测试通过，主线回归快照无漂移。
5. `P1-API/服务边界收口`：继续拆分 `backend/api/backtest_v2` 的混合职责，避免 API 包继续吸收应用编排。
6. `P1-文档与协议同步`：补齐目录树、架构文档、schema 文档、examples/runbook，并同步 OpenSpec delta spec。
7. `P1-验收`：文档与仓库现实一致，主线回归与产物协议检查通过。

回退策略：

- 每个波次独立提交与验证，任一波次若导致 `baseline_V10.1` 回归漂移或公共接口语义变化，即整波回退。
- 本轮不涉及数据库 schema 迁移和正式数据写口变更，因此回退以代码和文档回退为主。

## Open Questions

- `backend/core/cli` 在本轮结束时应保留为兼容 wrapper，还是直接退场为历史路径？
- 架构文档应以根目录 `ARCHITECTURE.md` 为主，还是以 `docs/` 下多文件拆分为主？
- 默认 `pytest` 通过条件是否仅要求 collect 成功，还是要同步纳入一组关键 smoke 替身测试？
