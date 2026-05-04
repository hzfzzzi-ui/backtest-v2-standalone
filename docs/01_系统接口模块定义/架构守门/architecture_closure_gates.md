# Architecture Closure Gates

## 1. 目的

本文定义当前主线接口与模块边界的收口门槛，用来判断新的接口或模块改动是否已经和当前正式主线一致。

## 2. 当前正式主线

- 前端正式 owner 链：`host.js -> runtime-surface.js -> app-shell.js`
- unified combo 正式执行合同：`execution_contract`
- 正式执行合同链：`execution_contract`、`subsystem_budget_v1`、`action_intent_v1`、`risk_override_v1`、`target_book_v1`、`execution_audit`
- `component_source_contract` 仅作为 provenance / assembly 说明保留
- 正式产物协议：`manifest.json`、`run_meta.json`、`rows`、`perf`、`nav`、`funnel`、`reason_codes`

## 3. 收口门槛

一次接口或模块改动要进入正式主线，至少满足：
1. 主文档已同步当前口径
2. `docs/01` 与 `docs/02` 的相关章节没有互相打架
3. 产物协议没有无声漂移
4. 前端和后端都消费同一套正式合同
5. 最小正式回归通过
6. 生产同环境 replay 不漂移

## 4. 阻塞条件

以下情况任意一条成立，都不能算收口完成：
- 主线里仍把非主实现文件写成 owner
- 主线里仍把 `component_source_contract` 或其它来源字段写成执行真相
- `run_meta` 或 `rows` 发生无声漂移
- 结果能跑但无法解释
- 文档和实现对不上
