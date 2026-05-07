# breakout-window-experiment Specification

## Purpose
Define the single-variable A/B experiment contract for `baseline_V10_2` breakout window changes.

## Requirements

### Requirement: V10.2 breakout window A/B 实验必须保持单一主改动
系统 MUST 提供一个以 `baseline_V10_2` 为锚点的 declarative study，用于比较 `breakout_window=45` 与 `breakout_window=40`。候选配置与 baseline 的差异 MUST 只允许出现在 `signal_generation.breakout.breakout_window`。

#### Scenario: Baseline 变体保持原值
- **WHEN** 系统为 `B0` 变体构造执行 payload
- **THEN** 该 payload MUST 继承 `baseline_V10_2` 的正式配置快照
- **THEN** 该 payload SHALL NOT 修改 `signal_generation.breakout.breakout_window`

#### Scenario: BW40 变体只修改 breakout window
- **WHEN** 系统为 `BW40` 变体构造执行 payload
- **THEN** 该 payload MUST 将 `signal_generation.breakout.breakout_window` 设为 `40`
- **THEN** 除该路径之外，股票池、成本、执行时点、排序、仓位和退出配置 MUST 与 `baseline_V10_2` 保持一致

### Requirement: V10.2 breakout window A/B 实验必须可复现执行
系统 MUST 通过 `research/studies/*.study.yaml` 和 generated thin script 提供统一入口，使同一代码快照下可以重复执行本次 A/B 实验。

#### Scenario: study dry-run 可检查执行计划
- **WHEN** 操作员对该 study 执行 `--dry-run`
- **THEN** 系统 MUST 输出包含 `B0` 与 `BW40` 两个变体的执行计划
- **THEN** 每个执行计划 MUST 明确 `config_json` 与窗口边界

#### Scenario: study run 复用正式 baseline 快照
- **WHEN** 操作员执行该 study
- **THEN** 系统 MUST 从 `outputs/baselines/baseline_V10_2/config.json` 读取锚点配置
- **THEN** 系统 SHALL NOT 通过当前主线配置文件重新推导 `baseline_V10.2`

### Requirement: V10.2 breakout window A/B 实验必须输出结构化对比结果
系统 MUST 为 `B0` 与 `BW40` 生成结构化实验产物和对比摘要，以便审计 `breakout_window` 变化对收益、回撤和行为诊断的影响。

#### Scenario: 运行 study 后生成两个实验结果
- **WHEN** study 执行完成
- **THEN** 系统 MUST 为 `B0` 和 `BW40` 各生成一个独立 `exp_id`
- **THEN** 每个变体 MUST 保留标准实验产物，例如 `perf.json`、`run_meta.json` 和配置快照

#### Scenario: 运行 study 后生成 compare 摘要
- **WHEN** study 执行完成
- **THEN** 系统 MUST 生成 machine bundle 与 human bundle
- **THEN** bundle MUST 暴露至少 `cagr`、`max_drawdown`、`sharpe`、`calmar`、`trades` 与 `turnover` 的对比结果
