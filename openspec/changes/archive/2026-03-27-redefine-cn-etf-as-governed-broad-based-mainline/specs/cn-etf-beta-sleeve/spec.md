## ADDED Requirements

### Requirement: ETF正式语义必须允许独立宽基主线而不是仅限辅助sleeve
`cn-etf-beta-sleeve` MUST 支持“受统一 Governor 管控的独立宽基轮动主线”语义。系统 SHALL NOT 再把所有 ETF 研究默认解释为个股 alpha 旁路的辅助配置层。

#### Scenario: ETF研究入口显式声明独立宽基主线角色
- **WHEN** 研究配置选择宽基 ETF 独立主线
- **THEN** `run_meta`、study 摘要和 audit MUST 将其角色标记为独立宽基主线
- **THEN** 系统 SHALL NOT 将其仅标记为辅助 beta sleeve

### Requirement: 宽基ETF主线必须使用独立的暴露翻译函数
当 `cn-etf-beta-sleeve` 以独立宽基主线运行时，系统 MUST 提供 sleeve-specific exposure policy，把统一 Governor 的状态与预算边界翻译为宽基 ETF 主线专属的 `target_exposure`、`min_deployable_exposure`、`controlled_accumulation_band` 和 `fallback_policy`。

#### Scenario: 宽基ETF主线不再默认复用个股alpha式部署语义
- **WHEN** 宽基 ETF 独立主线接收 Governor 的统一状态与预算边界
- **THEN** 系统 MUST 使用宽基 ETF 主线自己的暴露翻译函数
- **THEN** 系统 SHALL NOT 直接复用个股 alpha 或旧辅助 ETF sleeve 的默认部署语义
