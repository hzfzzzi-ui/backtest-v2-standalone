## Context

当前关于 moneyflow 的正式研究面主要还是 `a_share_moneyflow_divergence` 及历史 overlay study，缺少和 stock alpha / account state 对齐的 catalog、snapshot、study runner surface。与此同时，runtime 历史上又把 `mf_rank` 这个名字借给了综合 `final_score` 排序入口，导致 moneyflow 本体研究缺少稳定边界。

## Goals / Non-Goals

**Goals:**
- 建立研究层独立的 moneyflow factor catalog。
- 生成可审计的 moneyflow factor snapshots 与 score snapshots。
- 通过 `study_run` 提供正式的 moneyflow factor 研究入口。

**Non-Goals:**
- 不改变正式 runtime。
- 不把 moneyflow 因子默认接入候选排序。
- 不在这条 change 里重新定义策略基线。

## Decisions

### D1. 首版只做研究层，不碰 runtime
- 选择：复用现有 `a_share_moneyflow_divergence` 数据与 snapshot-backed 研究工作流，仅新增 catalog/snapshot/study surface。
- 原因：先把研究对象正式化，再决定是否入 runtime。
- 备选：直接把 high-bucket veto 接进 runtime。未选，因为缺少单独正式 surface。

### D2. 首版因子从 `monthly_divergence_rate` 开始
- 选择：先把仓库里已稳定存在、已被多轮研究使用的 monthly divergence 作为首版 moneyflow factor。
- 原因：这条因子已有数据依赖和研究共识，最适合收敛成正式 surface。
- 备选：一次性引入多个 moneyflow 衍生因子。未选，因为会放大口径和验证成本。

### D3. 沿用 factor snapshot/study runner 结构
- 选择：尽量复用 stock alpha factor 的研究结构，减少平台分叉。
- 原因：这符合前面三条平台 change 的方向。
- 备选：单独写 moneyflow 专用 runner。未选，因为会制造第二套研究入口。

## Risks / Trade-offs

- [风险] moneyflow 数据覆盖存在白名单约束。→ 通过沿用现有 coverage/gate 逻辑，把可用性写入 snapshot。
- [风险] 因子定义过早固化。→ 首版只收 `monthly_divergence_rate` 一个因子，后续再扩展。
- [风险] 用户误把研究 surface 当 runtime 能力。→ 在 spec 和输出中明确 `RESEARCH_ONLY`。
