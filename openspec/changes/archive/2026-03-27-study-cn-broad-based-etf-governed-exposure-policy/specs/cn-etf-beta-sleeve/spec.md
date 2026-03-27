## ADDED Requirements

### Requirement: cn_etf_beta 正式研究必须支持宽基 ETF 配置层暴露政策
当 `cn_etf_beta` 被用于宽基 ETF 正式研究时，系统 MUST 允许其使用宽基配置层暴露政策，而不是默认沿用个股 alpha 式的收缩语义。该政策 MUST 仍服从 Governor 的统一预算边界。

#### Scenario: 宽基 ETF 使用本地暴露翻译
- **WHEN** `cn_etf_beta` 被标记为宽基 ETF sleeve
- **THEN** 其目标暴露与最低可部署暴露 MUST 由宽基 ETF 本地 policy 决定
- **THEN** 其结果 MUST 明确说明这是宽基 ETF 暴露政策，而不是个股 alpha 默认语义

### Requirement: 本轮正式 ETF 研究范围必须限制为宽基 ETF
在本轮 change 中，`cn_etf_beta` 的正式研究范围 MUST 只覆盖宽基 ETF 与宽基风格指数 ETF。行业 ETF、主题 ETF 与窄行业 ETF SHALL NOT 进入本轮正式范围。

#### Scenario: 行业 ETF 请求被排除
- **WHEN** 研究配置试图把行业 ETF 作为本轮正式宽基研究输入
- **THEN** 系统 MUST 将其标记为超出本轮正式范围
- **THEN** 研究结论 SHALL NOT 把行业 ETF 结果混入宽基 ETF 主结论
