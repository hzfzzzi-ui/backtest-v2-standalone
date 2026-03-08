# BR35 Candidate Promotion

## ADDED Requirements

### Requirement: 新 candidate 必须从 ATR1.0 formal candidate 派生
系统 SHALL 以 `exp_20260307_171750033_eb7b` 的 resolved runtime config 作为 `v2-breakout-br35-atr10-candidate` 的锁定输入真值，而不是回到更早的原始 baseline。

#### Scenario: 从 ATR1.0 底座派生
- **WHEN** 系统构建 `v2-breakout-br35-atr10-candidate` 的运行时配置
- **THEN** 候选配置 SHALL 以 `exp_20260307_171750033_eb7b/run_config.json` 为源
- **THEN** 候选配置 SHALL 只允许 `strategy.params.breakout_window` 漂移

#### Scenario: 默认路径保持不变
- **WHEN** 请求未显式选择 `v2-breakout-br35-atr10-candidate`
- **THEN** 系统 SHALL 不得静默切换到 `breakout_window=35`

### Requirement: 新 candidate 必须附带 formal candidate 证据包
系统 SHALL 在写出 BR35 candidate 产物时附带完整证据包，覆盖全样本、局部稳健性、分阶段、终点敏感性与集中度。

#### Scenario: candidate 结果 ready
- **WHEN** BR35 candidate 运行完成且未发现审计阻断
- **THEN** 结果目录 SHALL 写出 `candidate_summary.json`、`candidate_summary.md`、`candidate_provenance.json`
- **THEN** 证据包 SHALL 引用 breakout_window 全样本和 robustness 结果

#### Scenario: candidate 审计阻断
- **WHEN** 发现非目标字段漂移或 `t+1` 审计失败
- **THEN** 系统 SHALL 阻止该结果标记为 `ready`

### Requirement: 新 candidate 必须可回退
系统 SHALL 保留旧 `v2-breakout-atr-stop-k10-candidate` 的入口与 identity，并允许用户停止使用 BR35 candidate 后回退到 ATR1.0 candidate 或更早 baseline。

#### Scenario: 停止使用 BR35 candidate
- **WHEN** 用户不再选择 `v2-breakout-br35-atr10-candidate`
- **THEN** 系统 SHALL 继续支持旧的 `v2-breakout-atr-stop-k10-candidate`
- **THEN** 历史产物 SHALL 不被重写
