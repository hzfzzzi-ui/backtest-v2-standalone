## Context

截至 `v2-script-migration-and-legacy-retirement-gate`：

- 公开产品表面已经收敛为 `config_json -> experiment_id -> manifest -> declared artifacts`
- internal helper 已经承接基线复跑、clean rerun、报告一致性等内部脚本
- `run_alpha_v1.py` 已被正式列入 `frozen legacy script`
- 第一批删除候选清单里，目前只有 `run_alpha_v1.py` 满足“零 live caller + 有替代路径 + 不影响基线门禁”的条件

因此，下一步不该继续停留在 freeze，而应执行第一批真正的 retirement。

## Goals / Non-Goals

**Goals:**
- 删除 `backend/scripts/run_alpha_v1.py`
- 让 active spec、测试和运维文档与“已退役”事实保持一致
- 用明确的 wave1 retirement ledger 记录删除证据和后续波次的进入条件
- 继续保证锁定基线 `exp_20260308_021045840_cde0` 的核心结果不变

**Non-Goals:**
- 本 change 不删除 `_experiment_runner_api`、`_config_governance`、`_candidate_presets`、`backtest_v2_artifacts`、`report_generator`
- 本 change 不修改回测计算逻辑、9-stage 口径、成交时点或数据库加载方式
- 本 change 不触碰仍有 live caller 的研究脚本
- 本 change 不做统一 archive；仅为后续批量 archive 做准备

## Decisions

### D1: retirement 按 wave 执行，而不是一口气清场

本 change 只执行 `wave1`，只删除已经满足证据门槛的对象。

选择理由：
- 这样可以保持“删除动作”与“证据充分性”一一对应
- 可以避免因为想快速清场而误删还在 live 的 shim 或研究脚本

拒绝的备选方案：
- 直接把所有冻结对象和 shim 一次性清掉
  - 拒绝，因为当前除 `run_alpha_v1.py` 外，其余对象仍有 live caller

### D2: `run_alpha_v1.py` 在 retirement 后不再保留 stub

wave1 的目标是“真正退役”，而不是把 frozen stub 再保留一轮。  
因此本轮会直接删除文件，而不是继续保留一个只会报错的脚本。

选择理由：
- frozen stub 适合作为迁移过渡，不适合作为长期终态
- 一旦删除门槛已满足，继续保留 stub 只会让 active tree 保留假入口

拒绝的备选方案：
- 继续保留只会 `SystemExit` 的文件
  - 拒绝，因为这会让“已退役”能力继续出现在 active 代码树里

### D3: active spec 必须跟随 retirement 同步收敛

当前 [alpha-experiment-runner spec](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/openspec/specs/alpha-experiment-runner/spec.md) 仍声明系统 SHALL 提供 `run_alpha_v1.py`。  
本 change 必须显式移除这条 active requirement。

选择理由：
- 否则 code truth 和 spec truth 会再次漂移
- archived change 和历史文档可以继续保留它曾经存在过的事实，但 active spec 不能继续把它当现行能力

### D4: archived 文档保留历史事实，不为 retirement 去重写历史

本 change 不修改 archive 下的历史 proposal/design/tasks。  
retirement 只更新 active spec 与当前运维文档。

选择理由：
- archived 变更应保留当时的历史事实
- 当前系统状态则由 active spec 和最新 ops 文档负责表达

### D5: wave1 继续受基线门禁保护

尽管本轮只删除一个冻结脚本，仍然必须运行同一套基线门禁。

选择理由：
- 这样可以确保“删除动作”不会通过测试遗漏意外影响结果口径
- 也保持所有 backend refactor wave 都受统一 contract 保护

## Risks / Trade-offs

- [风险] 删除 `run_alpha_v1.py` 后，仍有未识别的人工使用者找不到旧脚本
  -> Mitigation：在 retirement ledger 与 frozen doc 中保留替代路径；只删除已确认零 live caller 的脚本

- [风险] active spec 移除 requirement 后，历史读者误以为从未存在过这项能力
  -> Mitigation：不修改 archive 文档，只在 active spec 做 retirement delta

- [风险] 测试仍引用 frozen 行为，导致 retirement 后失败
  -> Mitigation：同步把测试从“断言 frozen 报错”改成“断言已退役/文件不存在/无 active caller”

## Migration Plan

1. 复核 `run_alpha_v1.py` 的零 live caller 证据
2. 删除脚本文件并清理 active tree 中的测试/文档引用
3. 更新 active spec，移除对 `run_alpha_v1.py` 的现行要求
4. 补充 wave1 retirement ledger
5. 运行 targeted checks 与基线门禁，确认核心结果不变

回滚策略：
- 如果删除后发现仍有 active caller，立即恢复文件删除操作，保留其 frozen 状态
- 如果删除影响基线门禁，立即回滚本 change，不触碰已完成的脚本治理与 public surface 收敛逻辑

## Open Questions

- wave2 是否优先处理 `run_breakout_next_stage_research.py` / `run_dynamic_sizing_experiments.py` / `run_market_state_segmentation_experiments.py` 对 `_experiment_runner_api` 的直连？
- 批量 archive 时，是否需要先统一做一次 main spec sync，再归档所有已完成的 refactor changes？
