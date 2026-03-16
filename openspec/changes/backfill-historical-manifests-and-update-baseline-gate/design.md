## Context

`multi-asset-entry-boundaries` 已让新实验在 `manifest.json`、`surface` 和 study 请求链中携带 canonical `asset_context`。但旧实验目录里的 `manifest.json` 仍停留在旧 schema，导致查询层只能在运行时做临时回填：HTTP `surface` 是正确的，磁盘上的 `manifest.json` 却不是最终真相。

同时，当前 baseline gate 仍锚定旧 contract：
- `backend/scripts/ops/v2_backend_refactor_baseline_contract.json` 仍记录旧 baseline 实验号；
- gate 仍把 `asset_scope` 这种已批准 schema enrichment、`run_config_hash` 因 canonical asset scope 带来的重算、以及 `portfolio_daily.csv` 新增诊断列导致的文件哈希变化，当成阻塞型失败。

本次 change 只处理这两件事，不触碰 runtime 行为、信号时点、成交时点和收益口径。

## Goals / Non-Goals

**Goals:**
- 为历史实验提供一次性的 canonical manifest 回填，让磁盘产物本身成为资产上下文真相。
- 更新 baseline gate contract，使其继续严格保护 `V10.1` 关键行为，同时允许已经批准的 schema 演进。
- 产出明确的回填审计结果和新的 baseline compare 结果。

**Non-Goals:**
- 不改 `V10.1` 的执行逻辑、信号逻辑和交易逻辑。
- 不修改前端结果面或 HTTP surface 主契约。
- 不引入新的资产类型实现，只处理当前 `cn_a_equity` 主线的历史产物回填。

## Decisions

### 决策 1：历史 manifest 采用离线回填，而不是继续依赖查询层临时推导

原因：
- 查询层临时推导只能保证接口响应正确，不能保证磁盘产物自描述。
- baseline gate、审计脚本和离线工具读的是文件本体，不能长期依赖 API 补丁。

备选方案：
- 保持现状，只在 `surface`/`history` 中补齐资产上下文。
  - 放弃原因：会让 manifest 本体长期失真，且 baseline gate 无法自然收口。

### 决策 2：baseline gate 继续以行为为阻塞门，但将已批准的 schema enrichment 显式转成 contract 规则

原因：
- `perf`、`nav`、`portfolio_trades`、`portfolio_candidates` 和 manifest 关键语义仍必须是阻塞门。
- `asset_scope`、`asset_context`、`run_config_hash` 因 canonical asset scope 引入的变化，属于结构升级，不应继续被误判为行为漂移。
- `portfolio_daily.csv` 已在前序 change 中加入诊断字段，继续用整文件哈希做阻塞门会把可解释性增强误判为失败。

备选方案：
- 直接放宽所有 `portfolio_daily`/`run_meta`/`config_truth` 对比。
  - 放弃原因：会把真正的代码漂移也一起放掉，削弱 `V10.1` 审计门。

### 决策 3：baseline contract 同步切到当前正式锚点

原因：
- 当前正式主线是 `baseline_V10.1 -> exp_20260314_144548534_7db9`。
- contract 文件仍指向旧 baseline 实验号，会让 gate 与当前主线脱节。

备选方案：
- 保留旧 baseline id，只在命令行 rerun 时覆盖。
  - 放弃原因：会让默认 gate 与人工口径不一致，不利于长期审计。

## Risks / Trade-offs

- [历史 manifest 推导不完整] → 仅允许从 `config.json`、`run_config.json`、`compiled_plan.json` 中推导 canonical `cn_a_equity` 资产上下文；无法可靠推导的实验跳过并写入审计报告。
- [gate 放宽过度] → 只把已批准的结构字段和 `portfolio_daily` 的新诊断列升级纳入 contract；`perf/nav/trades/candidates/manifest` 关键语义继续阻塞比较。
- [历史产物被误写] → 回填逻辑仅更新 `manifest.json` 缺失字段，不重写 `perf/nav/trades`，并输出 before/after 审计摘要。

## Migration Plan

1. 增加一个离线 manifest backfill 工具，对 `outputs/experiments/*/manifest.json` 做扫描与回填。
2. 先对当前 anchor `exp_20260314_144548534_7db9` 和其余历史实验执行回填，输出审计 JSON。
3. 更新 baseline contract：
   - baseline 实验号切到 `exp_20260314_144548534_7db9`
   - 允许字段与对比方式更新到 canonical 资产边界之后的 contract
4. 重跑 baseline regression compare，确认新的 contract 对 `V10.1` 结果给出正确结论。

回退思路：
- manifest 回填是确定性的，可按审计记录批量回滚或重新生成；
- baseline contract 是单文件更新，可直接回退到旧 JSON。

## Open Questions

- 是否把 `portfolio_daily` 从“整文件哈希门”降级为“关键列存在 + 行数/日期范围 + 核心聚合摘要”门；本 change 默认按这个方向设计。
- 对于缺少 `compiled_plan.json` 的极老实验，是否允许只写 `asset_scope=cn_a_equity` 而不写完整 `asset_context`；默认优先从现有 config/run_config 推导完整上下文，推导失败则记录跳过。
