## Why

锁定 baseline `exp_20260307_051743747_77d8` 之后，第一轮自主探索显示 `strategy.params.atr_stop_k=1.0` 是当前唯一同时改善 CAGR、MaxDD 与 Sharpe 的候选方向，但它的优势主要来自弱市阶段修复，尚不足以直接升级为新 baseline。现在需要一个受审计约束的候选升级流程，把该参数收敛为“正式候选”而不是“隐式默认值漂移”。

## What Changes

- 新增一条“baseline 候选升级”流程，只允许围绕单一主改动评估并落地研究优胜方案。
- 为 `breakout_trend` 的 `atr_stop_k=1.0` 建立正式候选定义，要求默认关闭、显式启用、可一键回退到锁定 baseline。
- 固化候选审计要求：不得修改手续费、滑点、股票池、成交规则、评价口径；若使用 `t` 日收盘生成信号，则仍需 `t+1` 执行。
- 要求候选方案在落地前保留审计证据，包括全样本结果、局部稳健性、分段窗口检查和终点敏感性检查。

## Capabilities

### New Capabilities
- `baseline-candidate-promotion`: 定义单参数研究优胜方案如何在不破坏锁定 baseline 的前提下被提升为正式候选、审计、回退和归档。

### Modified Capabilities
- `pipeline-data-integrity`: 补充候选运行时配置的最小漂移约束，确保候选只改变目标参数，其他字段与锁定 baseline 保持语义一致。

## Impact

- OpenSpec 变更工件：新增候选升级约束与任务拆解。
- 运行时配置编译与实验脚本：需要支持“默认 baseline / 显式候选”双轨，不得静默改写当前默认值。
- 审计与研究产物：需要输出或复用候选结论所需的对照摘要，便于后续实现前复核。
