## ADDED Requirements

### Requirement: research-only ETF 主线必须把正的 `TRANS_UP` 与 `RISK_OFF` 目标暴露转换为正的 live deploy target
当 `governed_a_share.etf_beta` 以 `governed_broad_based_standalone_mainline` / `broad_based_standalone_mainline_v1` 运行时，只要 `target_exposure > 0` 且不存在 hard block，系统 MUST 在 `TRANS_UP` 与 `RISK_OFF` 下生成正的 `deployment_pace`。系统 SHALL NOT 在 `RISK_OFF` 下仅因处于弱状态就把 research mainline 默认归零为 `RISK_OFF_ZERO`。

#### Scenario: TRANS_UP 正目标暴露生成正部署节奏
- **WHEN** research-only ETF 主线处于 `TRANS_UP`，且 `target_exposure > 0`，并且 Governor 未发出 hard block
- **THEN** `deployment_pace` MUST 大于 `0`
- **THEN** `pace_policy_gap` MUST 不得因为默认 floor-only 合同而系统性吞掉大部分 approved target

#### Scenario: RISK_OFF 正目标暴露不再被默认压成零
- **WHEN** research-only ETF 主线处于 `RISK_OFF`，且 `target_exposure > 0`，并且 Governor 未发出 hard block
- **THEN** `deployment_pace` MUST 大于 `0`
- **THEN** 研究视图 SHALL NOT 再把该日默认解释为 `RISK_OFF_ZERO`

### Requirement: research-only ETF 主线必须把 live target 压缩到最终可部署席位
当 research-only ETF 主线存在正的 `deployment_pace`，但实际选中 symbol 少于目标席位数时，系统 MUST 将 live deploy target 压缩到最终 selected/fallback symbol 集合，而不是把缺失席位对应的 approved target 静默丢弃。压缩后各 symbol 之间 SHALL 保持原始目标权重的相对比例。

#### Scenario: 两席目标但只选中一席
- **WHEN** research-only ETF 主线的 `target_selected_count=2`，但最终只有 1 个可部署 symbol
- **THEN** 该 symbol MUST 承接完整的 live deploy target
- **THEN** 系统 SHALL NOT 仅因为缺少第二席而把一半 approved target 留在现金

#### Scenario: fallback 参与 live target 压缩
- **WHEN** research-only ETF 主线因 under-filled deployment 激活 fallback symbol
- **THEN** fallback symbol MUST 参与 live deploy target 的最终压缩分配
- **THEN** `run_meta` 与 research audit MUST 能解释 fallback 参与后的最终 live target

### Requirement: research-only ETF 主线必须支持 `TRANS_UP` / `RISK_OFF` 的 state-change redeploy
当 research-only ETF 主线从其他状态切入 `TRANS_UP` 或 `RISK_OFF`，且无 hard block、当前实际暴露低于 live deploy target、并且存在可部署 symbol 时，系统 MUST 允许一次不等待下个 rebalance 周期的 redeploy。`RISK_OFF` 路径 MUST 仅允许 core-only redeploy。

#### Scenario: TRANS_UP 状态切换触发 redeploy
- **WHEN** research-only ETF 主线从 `{LIGHT, TRANS_DOWN, RISK_OFF, BULL}` 切入 `TRANS_UP`
- **THEN** 系统 MUST 允许一次 state-change redeploy
- **THEN** 研究视图 MUST 显式记录该 redeploy 的触发原因与执行路径

#### Scenario: RISK_OFF 仅允许 core-only redeploy
- **WHEN** research-only ETF 主线切入 `RISK_OFF` 且仍配置了正的目标暴露
- **THEN** 系统 MUST 仅对 core symbol 进行 redeploy
- **THEN** 系统 SHALL NOT 在 `RISK_OFF` 中恢复 growth seat

### Requirement: research-only ETF 主线必须对 `BULL / TRANS_UP` 输出可验收的目标/实际暴露收敛证据
当 `etf/cn_broad_based_research_mainline_r1` 运行 `2012-01-01` 到 `2026-03-24` 主窗口时，系统 MUST 在 `audit.json` 或等价研究审计产物中输出 `BULL / TRANS_UP` 的平均目标暴露、平均实际暴露与 gap 归因，并以此作为本 change 的验收依据。

#### Scenario: BULL 暴露偏差可审计
- **WHEN** 回测完成并生成 ETF research audit
- **THEN** 产物 MUST 能读取 `BULL` 的 `avg_target_exposure` 与 `avg_actual_exposure`
- **THEN** 产物 MUST 能解释两者差异主要来自 policy、timing 还是 residual

#### Scenario: TRANS_UP 暴露偏差可审计
- **WHEN** 回测完成并生成 ETF research audit
- **THEN** 产物 MUST 能读取 `TRANS_UP` 的 `avg_target_exposure` 与 `avg_actual_exposure`
- **THEN** 产物 MUST 能据此判断本轮是否达到 `<= 0.10` 的偏差目标
