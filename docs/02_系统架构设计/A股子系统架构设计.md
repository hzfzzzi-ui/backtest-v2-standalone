# A股子系统架构设计

## 0. 文档定位

本文档描述当前 A 股子系统的正式架构边界，覆盖：

- A 股个股子系统
- ETF 子系统
- 两者与市场状态、组合总控、执行内核、审计层之间的关系

## 1. 当前正式范围

当前正式范围包括六层：

1. 市场状态引擎
2. 组合总控
3. A 股个股子系统
4. ETF 子系统
5. 共享执行内核
6. 正式审计

当前正式收益锚点：

- `baseline_V10.1`

## 2. 子系统定位

- A 股个股子系统承担当前正式 alpha 主线
- ETF 子系统承担受控 beta 暴露与有限防守补充
- ETF 子系统不是独立收益主线，也不是第二套状态机

## 3. 正式合同

当前与 A 股 unified combo 直接相关的正式合同：

- `execution_contract`
- `action_intent_v1`
- `risk_override_v1`
- `target_book_v1`

说明：

- `execution_contract` 是 unified combo 当前唯一正式执行合同
- `comboTruth` 是结果展示真相，不是执行合同
- `component_source_contract` 是装配与 provenance 元数据，不是执行合同

## 4. Unified combo 当前口径

`A_STOCK_ETF_V1` 的收口目标应理解为：

- 顶层 wrapper 可包含 `asset_scope`、`asset_context`、`unified_runtime`
- 运行前必须先把组件配置解析为唯一 `execution_contract`
- 组件来源说明保留在 provenance 区
- 组件实验引用通过 `component_experiments` 或等价 provenance 字段追踪

## 5. 代码映射

主路径主要位于：

- `backend/core/services/cn_stock_etf_unified_runtime_service.py`
- `backend/api/backtest_v2/runner_config_bundle.py`
- `frontend/assets/js/desktop-shell/config-workspace.js`
- `frontend/assets/js/desktop-shell/run-orchestration.js`
- `frontend/assets/js/desktop-shell/results-workspace.js`
- `frontend/app/results-workbench/`

## 6. 当前收口方向

当前文档口径要求：

- unified combo 主运行必须收口到唯一 `execution_contract`
- 前端来源展示不得覆盖执行真相
- `component_source_contract` 只保留为 assembly/provenance
- `component_experiments` 只保留为引用追踪
