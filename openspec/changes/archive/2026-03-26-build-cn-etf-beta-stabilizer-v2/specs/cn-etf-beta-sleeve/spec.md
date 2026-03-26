## ADDED Requirements

### Requirement: ETF beta 稳定器 V2 研究线必须收敛到双宽基主候选
当 `cn_etf_beta` 进入稳定器 V2 研究线时，系统 MUST 将正式主候选池收敛为 `510300.SH` 与 `510050.SH`，并 SHALL 将 `511010.SH` 仅作为 sleeve-local fallback 研究资产，而不是正式核心 beta 候选。

#### Scenario: V2 研究线构建主候选池
- **WHEN** 系统按 ETF 稳定器 V2 规则构建研究入口
- **THEN** 正式 core beta 主候选 MUST 仅包含 `510300.SH` 与 `510050.SH`
- **THEN** 系统 SHALL NOT 将 `510500.SH`、`512100.SH` 或 `512890.SH` 静默保留在 V2 主候选池中

#### Scenario: fallback 资产不伪装成 core beta
- **WHEN** `511010.SH` 被纳入 ETF 稳定器 V2 研究配置
- **THEN** 系统 MUST 将其标记为 fallback 资产
- **THEN** 产物 MUST 能区分“core beta 持仓”和“fallback 持仓”

### Requirement: ETF beta 稳定器 V2 必须支持小规模并持
ETF 稳定器 V2 MUST 支持 `max_selected_symbols = 2` 的小规模并持语义，以避免继续把 ETF sleeve 实现为单标的战术轮动小仓。

#### Scenario: V2 允许双宽基并持
- **WHEN** 同一调仓日 `510300.SH` 与 `510050.SH` 同时满足 V2 规则
- **THEN** 系统 MUST 允许两只 ETF 在同一 sleeve 内并持
- **THEN** 产物 MUST 暴露最终选中数量与各自权重或份额语义

#### Scenario: V2 仍可退化为单标的
- **WHEN** 只有一只 core beta ETF 满足 V2 规则
- **THEN** 系统 SHALL 允许退化为单标的部署
- **THEN** 产物 MUST 能说明另一只未部署的原因

### Requirement: ETF beta 稳定器 V2 必须显式暴露部署不足原因
ETF 稳定器 V2 MUST 在产物中显式暴露 under-deploy 原因，至少包括：
- 绝对过滤后无合格 core beta
- Governor 压缩预算
- 可部署 slot 不足
- fallback 触发

#### Scenario: 因绝对过滤导致未部署
- **WHEN** 调仓日没有任何 core beta ETF 通过绝对过滤
- **THEN** 产物 MUST 给出明确的 reason code
- **THEN** 产物 MUST 能区分是回现金还是进入 fallback

#### Scenario: 因 Governor 压缩导致部署偏低
- **WHEN** ETF 稳定器 V2 的理论可部署标的多于实际部署标的
- **THEN** 产物 MUST 暴露 Governor 预算或 deployability 的压缩原因
- **THEN** 研究审计 MUST 能引用该证据而不是反推
