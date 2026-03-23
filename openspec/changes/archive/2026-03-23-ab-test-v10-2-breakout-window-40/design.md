## Context

当前 `baseline_V10.2` 的正式锚点配置位于 `outputs/baselines/baseline_V10_2/config.json`，其中 `signal_generation.breakout.breakout_window = 45`。这类参数属于 L3 研究口径，不能直接改正式 baseline，也不适合用手工 JSON 覆盖临时跑两次，因为那样难以复现、也难证明只改了一个主变量。

仓库已经提供 `research/studies/*.study.yaml`、`backend.cli study_run` 和 generated thin script 这套研究入口，可以在继承 baseline 配置的前提下，用 `config_patches` 精确施加单个参数变更，并自动产出 compare、machine bundle、human bundle。

## Goals / Non-Goals

**Goals:**
- 以 `baseline_V10_2` 为锚点，固定 `2012-01-04 ~ 2026-03-20` 窗口，做 `45` 对 `40` 的单变量 A/B。
- 确保候选版除了 `signal_generation.breakout.breakout_window` 之外，不发生其它配置漂移。
- 复用现有 study runner 和 compare 产物，输出可复现的结论。

**Non-Goals:**
- 不直接修改正式 `baseline_V10_2` 配置。
- 不把 `40` 自动登记为新 baseline。
- 不在这次变更里扩展到三窗口 gate 或其它 breakout 参数联动实验。

## Decisions

### 1. 用 declarative study，而不是手工改配置

采用 `research/studies/v10/*.study.yaml` 加 generated thin script。

原因：
- 能复用现有研究入口与 compare 输出；
- 能把差异限制在 `config_patches`；
- 能用 `--dry-run` 先检查执行 payload，避免隐性漂移。

备选方案：
- 直接复制 baseline JSON 手工改值再跑两次。放弃原因是复现性差，而且很难证明只改了一个字段。

### 2. 锚点固定为 `outputs/baselines/baseline_V10_2/config.json`

study 直接从正式 baseline 快照读取配置，并通过 `metadata.materialize_config_json: true` 把候选配置固化到 request payload 中。

原因：
- 避免回看当前主线配置；
- 让 A/B 两边都以相同的 baseline 快照为真相源。

### 3. 本次只跑 `2012-01-04 ~ 2026-03-20` 的全窗口 A/B

本次窗口与当前 `baseline_V10.2` 最新正式重跑保持一致，只做单窗口对照。

原因：
- 用户当前需求是“做一版 A/B 测试”，不是新的正式升格流程；
- 先看全窗口行为差异，再决定是否值得升级到多窗口 gate。

### 4. 运行时跳过 baseline append

执行 study 时使用 `--skip-baseline-append`。

原因：
- 本次只是参数探索，不应把未决候选自动写入 baseline 台账；
- 仍保留 machine/human bundle 与 compare 产物用于审计。

## Risks / Trade-offs

- [风险] 单窗口 A/B 不能替代正式三窗口判断
  → Mitigation：在结论里明确这只是探索性结果，若 `40` 显著占优再升级到多窗口研究。

- [风险] 当前 V2 数据状态会直接影响对比结果
  → Mitigation：A 与 B 在同一时点、同一数据口径、同一代码快照下连续运行。

- [风险] study 定义未来被无意改成多变量
  → Mitigation：增加一个最小研究契约测试，锁定候选版只改 `breakout_window`。
