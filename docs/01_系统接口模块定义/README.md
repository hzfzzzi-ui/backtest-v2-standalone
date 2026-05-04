# 01 系统接口模块定义

本目录只定义当前主线的接口与模块边界，不承载重构过程叙事。

## 当前正式口径

- 前端正式 owner 链：`host.js -> runtime-surface.js -> app-shell.js`
- unified combo 与单次回测的唯一正式执行真相：`execution_contract`
- 正式执行合同链：`execution_contract`、`subsystem_budget_v1`、`action_intent_v1`、`risk_override_v1`、`target_book_v1`、`execution_audit`
- `component_source_contract`、`baseline_id`、`study_id`、`linked_exp_id` 只属于 provenance / assembly 说明
- 已废弃组合源字段不再属于主合同
- `outputs/` 中的运行产物不是源码主路径

## 目录说明

- `共享层/`：A 股主线与多 sleeve 共用的正式接口合同
- `A股个股子系统/`：A 股个股主线接口定义
- `A股ETF子系统/`：A 股 ETF 子系统接口定义
- `产物协议/`：`manifest`、`rows`、`run_meta` 等结果协议
- `架构守门/`：当前架构边界与变更门槛

## 读取顺序

先看共享层，再看两个子系统，再看产物协议，最后看架构守门。
