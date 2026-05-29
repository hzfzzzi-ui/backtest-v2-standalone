## Why

当前 `backtest_V2_standalone` 与 `pams` 都包含研究、调仓、账户和通知相关逻辑，系统边界已经混杂；如果继续在两个仓库里并行扩展，后续 live 策略调仓、资产真值、审批和执行状态会产生口径漂移。

本变更先冻结跨系统架构合同：`backtest_V2_standalone` 演进为专业量化研究平台，`pams` 演进为个人资产管理系统；正在实盘的策略只能通过正式调仓包向 PAMS app/web 推送仓位调整信息。

## What Changes

- 明确双系统职责边界：
  - 量化研究平台负责市场数据口径、研究实验、baseline、live strategy 注册、每日 live run、调仓包生成和研究审计。
  - PAMS 负责账户、持仓、现金、交易生命周期、app/web 展示、通知推送、用户审批和执行状态回写。
- 新增 `daily_position_adjustment_package@1` 作为两个系统之间的正式合同，禁止 PAMS 直接复算研究策略。
- 新增 live strategy 发布门禁：只有标记为 `live_approved` 的策略可以生成并推送正式调仓包；shadow、AB、research-only 实验不得进入 PAMS 主通知流。
- 新增 PAMS 入站信号接收边界：PAMS 接收、校验、幂等入库、生成通知和交易生命周期草稿，但不拥有策略计算逻辑。
- 收口现有过渡链路：
  - `outputs/mobile_ops/*`、`outputs/ops/sim_account/*` 只能作为兼容镜像或审计产物，不作为跨系统长期接口。
  - `pams` 中旧策略扫描、旧回测和复制版 `backtest_V2` 逻辑应冻结为 legacy，后续不再承接主线研究能力。
- **BREAKING**: 架构语义上，PAMS 不再被允许作为策略研究与选股来源；研究平台移动端审批/执行链路不再作为长期产品主边界，只保留过渡或内部预览角色。

## Capabilities

### New Capabilities

- `quant-platform-pams-boundary`: 定义量化研究平台与 PAMS 的职责、数据真值和禁止越界规则。
- `live-strategy-publish-contract`: 定义 live strategy 注册、发布门禁、每日运行和禁止 shadow 推送的合同。
- `daily-position-adjustment-package`: 定义每日调仓包 schema、幂等键、来源痕迹、风险标记和失败模式。
- `pams-live-signal-ingestion`: 定义 PAMS 接收调仓包、入库、通知、审批草稿和状态回写边界。

### Modified Capabilities

- `position-aware-reconcile-run`: reconcile run 的 action sheet 可以作为调仓包来源，但仍是派生分析结果，不得升格为账户或交易真值。
- `transaction-lifecycle-domain`: 交易生命周期主表必须保留调仓包来源痕迹，并成为 PAMS 审批、提交、成交、拒绝、撤销的长期真值。
- `mobile-order-approval`: 移动端审批的长期主读写边界迁移到 PAMS 事务域；研究平台文件型 approval ticket 仅保留为过渡兼容产物。

## Impact

- 影响仓库：
  - `C:\Users\hzfzzzi\openclaw\backtest_V2_standalone`
  - `C:\Users\hzfzzzi\openclaw\pams`
- 预期影响路径：
  - `openspec/changes/split-quant-platform-and-pams-live-signal-contract/`
  - `backend/core/services/sim_account_reconcile_service.py`
  - `backend/core/services/mobile_*`
  - `backend/api/mobile`
  - `backend/api/backtest_v2`
  - `research/studies`
  - `C:\Users\hzfzzzi\openclaw\pams\backend\api`
  - `C:\Users\hzfzzzi\openclaw\pams\backend\scheduler`
  - `C:\Users\hzfzzzi\openclaw\pams\database\postgres\schema`
- 不应影响：
  - 当前 baseline 主逻辑、信号时点、成交时点、benchmark/regime 定义。
  - A 股研究三窗口纪律。
  - `outputs/` 作为运行产物而非源码主路径的边界。
- 主要风险：
  - 双系统同时保留策略逻辑导致口径漂移。
  - 文件产物被误用为长期跨系统 API。
  - PAMS 旧表名和研究平台当前 `pams_*` 数据源命名混淆。
  - live 调仓包缺少幂等和来源哈希，导致重复通知或无法审计。
