# ARCHITECTURE_GUARDRAILS

## 1. 目标

本文约束当前仓库的正式接口、模块边界和变更方式。它只描述当前真实主线，不维护重构历史叙事。

## 2. 当前正式边界

- 前端主装载链是 `host.js -> runtime-surface.js -> app-shell.js`
- unified combo 与单次回测的正式执行真相是 `execution_contract`
- 执行正式合同链是 `execution_contract`、`subsystem_budget_v1`、`action_intent_v1`、`risk_override_v1`、`target_book_v1`、`execution_audit`
- `component_source_contract` 只允许作为 provenance / assembly metadata 存在
- `manifest.json`、`run_meta.json`、`rows` 是当前正式产物协议的核心部分

## 3. 稳定规则

- 接口可以新增字段，但不能无声删字段
- 数值字段必须可序列化为 JSON number 或 null
- 不允许把研究旁路写成正式主合同
- 不允许把历史产物目录当源码主路径
- 不允许用前端兜底掩盖后端协议漂移

## 4. 不应留在主线的内容

- 非主实现 owner 叙事
- 过时兼容叙事
- 已废弃字段当作当前真相
- 只属于重构过程的临时说明
