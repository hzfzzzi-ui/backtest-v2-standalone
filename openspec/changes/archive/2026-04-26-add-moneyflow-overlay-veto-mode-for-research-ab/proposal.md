# Proposal

## Why

当前 `moneyflow overlay` 只支持 `shadow / tiebreak / soft_weight`，不支持最小研究 A/B 所需的 `veto` 接法。继续用现有模式会把“因子是否有效”和“接法是否失真”混在一起，结果无法归因。

## What Changes

- 为股票腿研究 A/B 增加最小 `moneyflow overlay veto` 模式
- 仅在候选计划层生效
- 不改主排序、不改退出、不改 ETF/defense 行为

## Scope

- `backend/core/portfolio/candidate_plan.py`
- focused unit tests

## Out of Scope

- 不扩 semantic schema
- 不改正式主线默认值
- 不把 moneyflow 因子接进组合主线
