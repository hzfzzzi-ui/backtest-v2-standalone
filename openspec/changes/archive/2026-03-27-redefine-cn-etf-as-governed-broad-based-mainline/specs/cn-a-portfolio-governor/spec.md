## ADDED Requirements

### Requirement: Governor必须区分统一真相与宽基ETF主线的本地表达
当宽基 ETF 作为独立主线运行时，`cn-a-portfolio-governor` MUST 只负责输出统一状态真相、总风险边界和禁做区间；Governor SHALL NOT 直接把宽基 ETF 压成与个股 alpha 相同的风格暴露表达。宽基 ETF 主线的实际进入、退出和承接表达 SHALL 在 Governor 边界内由其本地 policy 决定。

#### Scenario: Governor为宽基ETF主线提供边界而不是替代其策略
- **WHEN** Governor 计算某交易日宽基 ETF 主线的预算与状态边界
- **THEN** Governor MUST 输出该主线可消费的统一边界
- **THEN** Governor SHALL NOT 越权替代宽基 ETF 主线的本地 enter/exit 决策

### Requirement: Governor必须显式暴露宽基ETF主线的允许带宽
当宽基 ETF 作为独立主线运行时，Governor 输出 MUST 显式暴露可部署带宽、禁做带宽以及允许承接的状态区间，供 ETF 主线进行 sleeve-specific 翻译。

#### Scenario: Governor显式说明宽基ETF主线能否承接
- **WHEN** Governor 输出某交易日对宽基 ETF 主线的预算摘要
- **THEN** 摘要 MUST 能区分当前是完全禁做、正常部署还是允许受控承接
- **THEN** 下游 audit MUST 能引用这些字段解释 ETF 主线为何持有、减持或承接
