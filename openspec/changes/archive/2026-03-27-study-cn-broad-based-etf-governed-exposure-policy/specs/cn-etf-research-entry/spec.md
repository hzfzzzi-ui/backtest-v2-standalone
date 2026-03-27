## ADDED Requirements

### Requirement: cn_etf 研究入口必须提供仅覆盖宽基 ETF 的正式研究入口
`cn_etf` 研究入口 MUST 为本轮 change 提供一个仅覆盖宽基 ETF 的正式研究入口或 preset。该入口 MUST 明确排除行业 ETF，并将本轮研究标记为宽基 ETF governed exposure policy。

#### Scenario: 宽基研究入口显式排除行业 ETF
- **WHEN** 用户选择本轮宽基 ETF 正式研究入口
- **THEN** 系统 MUST 只展开宽基 ETF 与宽基风格指数 ETF 候选范围
- **THEN** 系统 SHALL NOT 静默把行业 ETF 混入该入口

#### Scenario: 研究入口暴露本轮角色语义
- **WHEN** 产物记录本轮研究入口元信息
- **THEN** `run_meta` 或等价元信息 MUST 能说明该入口属于宽基 ETF governed exposure policy
- **THEN** 系统 MUST 能区分它与旧 ETF V1、A0 模板或行业 ETF 研究入口
