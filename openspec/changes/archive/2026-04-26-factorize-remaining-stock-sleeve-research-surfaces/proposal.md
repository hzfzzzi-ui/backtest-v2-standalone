# Proposal

## Why

当前主线股票腿已经拆出了：

- stock alpha 原子因子
- final score 组成项
- risk gate
- positive quality
- 第一版 exit fragility

但剩余三条关键研究线还没独立化：

1. 负向条件上下文
2. 行业二阶段
3. 执行压力

如果这三条不拆出来，当前主线仍然无法完整解释为“状态过滤 + 质量项 + 条件上下文 + 持仓/执行约束”的系统。

## What Changes

- 新增 `negative conditional context` research surface
- 新增 `industry second stage` research surface
- 新增 `execution pressure` research surface
- 接入 `study_runner`
- 新增基于当前策略基线的真实三窗口 study

## Scope

本 change 仅限：

- `backend/research`
- `research/studies/factors`
- `openspec/changes/factorize-remaining-stock-sleeve-research-surfaces`

不包含：

- 正式主线 runtime 行为修改
- 预算/下单/执行逻辑修改
- ETF / defense 线拆分

## Risk

- `negative conditional context` 和 `execution pressure` 本质上更像条件/上下文，不能误读成正向横截面 rank 因子
- `execution pressure` 研究面基于 stock sleeve `portfolio_daily.csv`，不等于组合层执行压力
- 本 change 只提供研究面和结论，不自动提升任何主线默认值
