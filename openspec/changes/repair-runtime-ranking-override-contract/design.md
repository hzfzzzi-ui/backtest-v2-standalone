## Context

当前仓库里，排序相关执行真相按架构应当只有一条：

- 进入 execution shell 的正式真相只能是 `RuntimePlan.execution_overrides` / `execution_contract`

但现状是 direct runtime-config path 还残留了一套 legacy 输入字段：

- `runtime_config.strategy.params.ranking_mode`
- `runtime_config.strategy.params.enable_residual_ranking`

compile path 已经会在上游把这些 legacy 字段规范化成 `execution_overrides.enable_multifactor_rank`；direct runtime-config path 则没有完成这一步，导致同一条 live baseline 在不同入口表现不一致。当前 `baseline_V10_1` live-like `B0/A1` 完全相同，就是这个“规范化缺失”而不是“双真相合理存在”的直接证据。

## Goals / Non-Goals

**Goals:**

- 让 direct runtime-config path 在构建 `RuntimePlan` 时完成与 compile path 等价的排序字段规范化。
- 保持显式 `execution_overrides` 优先级最高，不反向覆盖用户或调用方已经明确给出的值。
- 让修复后的行为能通过 `B0 / A1_NO_RESIDUAL_RANK` 最小复跑直接验证。

**Non-Goals:**

- 不修改 `baseline_V10_1` 配置内容。
- 不修改因子定义、`candidate_plan` 排序实现、`market_filter_gate`、风险 gate 或 exit 栈。
- 不顺手统一所有排序 helper 的历史重复实现；本次只修合同缺口。

## Decisions

### 1. 只允许 `execution_overrides` 成为排序执行真相

选择在 `build_foundation_runtime_plan()` 构建 `RuntimePlan` 时做一次性规范化，而不是让 foundation shell 在运行阶段边消费边推断。

原因：

- 这里是 legacy backend runtime config 进入正式执行真相的最后组装边界。
- 在这里修，能同时覆盖 baseline replay、study run、脚本调用等所有 direct runtime-config path。
- 规范化完成后，execution shell 仍只消费一份 `execution_overrides`，不会再保留“双来源并行生效”。

备选方案：

- 只修 `study_runner`：范围太窄，baseline replay 与脚本仍会继续漂移。
- 在 `run_foundation_execution_shell()` 中临时推断：会把 legacy 字段和 `execution_overrides` 变成并列真相，违背单一执行真相原则。

### 2. legacy `runtime_config` 只作为规范化输入，不作为并列执行来源

规范化逻辑采用：

- 先从 legacy `runtime_config.strategy.params` 提取兼容输入
- 在 `RuntimePlan.execution_overrides` 中一次性写成正式执行真相
- 再叠加显式 `overrides`

这样可以保证：

- `ranking_mode=residual_only`、`enable_residual_ranking=true` 这类已有 legacy 配置会真正进入正式执行真相
- 如果调用方显式传入 `enable_multifactor_rank=false`，仍以显式关闭为准

### 3. 派生范围只覆盖当前已被 compile path 承认的排序相关字段

本次从 runtime config 派生：

- `enable_multifactor_rank`
- `momentum_top_pct`
- `enable_strength_rank`
- `strength_ma`
- `strength_top_k_mode`
- `mf_topk`

原因：

- 这些字段已经有现成 compile-path 语义，不引入新排序概念
- 足够让 `residual_only`/`enable_residual_ranking` 路径与 compile path 等价

## Risks / Trade-offs

- [Risk] 修复后当前 live-like A 股主线路径会第一次真正进入排序分支，结果会变化。  
  → Mitigation：只重跑 `B0 / A1_NO_RESIDUAL_RANK`，先验证行为差异与计数器，再决定是否扩大复跑范围。

- [Risk] runtime config 中若存在历史脏字段，派生逻辑可能放大旧配置影响。  
  → Mitigation：只读取 compile path 已经承认的少量字段，并保持显式 override 优先。

- [Risk] compile path 与 direct runtime-config path 仍各自维护一份 legacy 规范化逻辑，后续可能再次漂移。  
  → Mitigation：本次先完成最小修复；若后续继续演进排序合同，再单开 change 收拢到共享 helper。
