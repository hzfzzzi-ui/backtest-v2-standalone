## ADDED Requirements

### Requirement: 正式 ETF 研究入口必须收敛到 Phase 1 配置引擎入口
当 `cn_etf` 以 `formal_mainline` 方式被消费时，系统 MUST 将研究入口收敛到 Phase 1 配置引擎入口，而不是继续把研究轮动模板作为正式主线入口。

#### Scenario: 正式主线入口固定
- **WHEN** 用户或系统请求运行正式 ETF 主线
- **THEN** 入口 MUST 指向 Phase 1 正式配置引擎
- **THEN** 研究轮动模板 SHALL NOT 被默认当成正式主线入口

### Requirement: 正式 ETF 研究入口必须显式区分 formal_mainline 与 research_only
`cn_etf` 研究入口 MUST 显式区分正式主线入口与研究分支入口，避免历史轮动模板继续被误用成正式 ETF 主线。

#### Scenario: 入口层显式区分正式与研究
- **WHEN** 系统列出 ETF 可运行 study 或 preset
- **THEN** 正式主线入口 MUST 被标记为 `formal_mainline`
- **THEN** 历史研究分支 MUST 被标记为 `research_only` 或 `do_not_promote`
