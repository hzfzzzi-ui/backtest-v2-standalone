## MODIFIED Requirements

### Requirement: 系统必须提供首波 ETF 最小研究 preset
系统 MUST 为首波 ETF 提供最小研究 preset，至少包括 `cn_etf_single_asset_template`、`cn_etf_first_wave_core` 和 `cn_etf_first_wave_all`。这些 preset MUST 复用现有研究总线与产物协议，但 SHALL NOT 直接修改 `baseline_V10.x` 的正式个股主逻辑。系统 MUST 允许在受控目录内新增 research-only ETF 主线 preset，并要求该类 preset 的正目标暴露在 runtime 产物中可验证其 deployability，而不是只停留在 config snapshot。

#### Scenario: 核心批次 preset 展开
- **WHEN** 用户选择 `cn_etf_first_wave_core`
- **THEN** 系统 MUST 生成仅包含 `510300.SH`、`510500.SH`、`510050.SH`、`518880.SH`、`511010.SH` 和 `512100.SH` 的研究配置
- **THEN** 该研究配置 MUST 保持 ETF 资产上下文而不是回落到 A 股个股上下文

#### Scenario: 全批次 preset 展开
- **WHEN** 用户选择 `cn_etf_first_wave_all`
- **THEN** 系统 MUST 生成包含全部 9 只 ETF 的研究配置
- **THEN** 该配置 MUST 可被实验总线直接消费并产出标准研究产物

#### Scenario: research-only 主线 preset 输出可部署证据
- **WHEN** 用户运行 `etf/cn_broad_based_research_mainline_r1` 这类 research-only ETF 主线 preset
- **THEN** `run_meta` 与 `audit` MUST 能同时暴露 `target_exposure`、`deployment_pace`、`execution_path` 与 `actual_exposure`
- **THEN** 系统 SHALL NOT 仅输出 config 中的目标暴露而缺失其是否真正被部署的证据
