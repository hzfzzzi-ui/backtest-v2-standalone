# Design

## Goal

提供一个仅用于研究 A/B 的最小 veto 接法，使 `monthly_divergence_rate` 能按底部分桶剔除候选，而不引入新的排序主干。

## Design

- 复用现有 `asset_context.moneyflow_overlay.mode`
- 新增字符串模式：
  - `veto_bottom20`
  - `veto_bottom30`
- 在候选计划层读取 `overlay_score`
- 对当天可用候选按 `overlay_score` 升序排序
- 剔除底部指定比例候选，写入 `MONEYFLOW_OVERLAY_VETO`

## Constraints

- 仅影响 `build_candidate_plan`
- 维持 `shadow / tiebreak / soft_weight` 原行为不变
- 不新增配置字段，避免 schema 扩散
