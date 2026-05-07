## ADDED Requirements

### Requirement: cn_etf research entry MUST 支持 ETF research mainline R1 preset
`cn_etf` research entry MUST 支持装载 `etf/cn_broad_based_research_mainline_r1`，并将其视为受控目录内的 research-only study preset。该 preset MUST 可由 `study_runner` 与 generated thin script 直接执行。

#### Scenario: study_runner 装载 R1 preset
- **WHEN** 用户通过 study id `etf/cn_broad_based_research_mainline_r1` 运行研究
- **THEN** 系统 MUST 能从 `research/studies/etf/` 装载对应 study yaml
- **THEN** 系统 MUST 生成可直接执行的 request payload

#### Scenario: generated thin script 指向 R1 preset
- **WHEN** 用户运行 `backend/scripts/generated/run_etf_cn_broad_based_research_mainline_r1.py`
- **THEN** 脚本 MUST 将执行入口转发到 `study_run etf/cn_broad_based_research_mainline_r1`
- **THEN** 脚本 SHALL NOT 内嵌策略实现逻辑
