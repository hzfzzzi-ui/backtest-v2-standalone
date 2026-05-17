## ADDED Requirements

### Requirement: ETF shadow research pool MUST be versioned and research-only
系统 MUST 为 ETF 扩池研究维护显式版本化的 research-only shadow pool。`cn_etf_research_shadow_pool_v1` SHALL NOT 改变 `formal_etf_pool_v1`、当前 live baseline、正式 ETF sleeve 默认候选池或正式组合运行口径。

#### Scenario: shadow pool is selected for research
- **WHEN** 研究配置选择 `cn_etf_research_shadow_pool_v1`
- **THEN** 运行元信息 MUST 标记 `pool_version = cn_etf_research_shadow_pool_v1`
- **THEN** 运行元信息 MUST 标记 `research_only = true`
- **THEN** 系统 SHALL NOT 将该 pool 视为 `formal_etf_pool_v1`

### Requirement: ETF shadow pool v1 MUST define explicit symbol roles
`cn_etf_research_shadow_pool_v1` MUST 明确候选标的及其研究角色。初始候选 SHALL 包含 `510880.SH`、`512890.SH`、`518880.SH`、`159915.SZ`、`588000.SH` 和 `159845.SZ`，并分别标记为红利/价值、红利低波对照、黄金防守、成长、科创成长和中证1000替代候选。

#### Scenario: shadow pool role map is materialized
- **WHEN** 系统展开 `cn_etf_research_shadow_pool_v1`
- **THEN** 输出候选清单 MUST 包含每个 ETF 的 `ts_code`
- **THEN** 输出候选清单 MUST 包含每个 ETF 的 `shadow_role`
- **THEN** `159845.SZ` MUST 被标记为 `512100.SH` 的替代候选而不是新增小盘风险预算

### Requirement: deferred ETF candidates MUST stay out of shadow pool v1
系统 MUST 将现金/久期候选、跨境 ETF 和行业/主题 ETF 明确排除在 `cn_etf_research_shadow_pool_v1` 之外，除非后续 change 定义对应的数据、会计和交易语义。

#### Scenario: deferred candidate is requested in shadow pool v1
- **WHEN** 用户或配置请求将 `511880.SH`、`511260.SH`、`513500.SH`、`513100.SH` 或行业/主题 ETF 纳入 `cn_etf_research_shadow_pool_v1`
- **THEN** 系统 MUST 拒绝或标记为 deferred
- **THEN** 拒绝原因 MUST 指向现金/久期、跨境或行业主题语义未定义

### Requirement: shadow pool experiments MUST report coverage and promotion eligibility
使用 shadow pool 的实验 MUST 输出每个候选的 coverage window、数据可用性、formal eligibility、promotion gate 状态和 reject reason。短历史候选 SHALL 保留在 shadow diagnostics 中，但不得被视为已通过完整三窗口门槛。

#### Scenario: short-history ETF participates in diagnostics
- **WHEN** `588000.SH` 或 `159845.SZ` 因上市时间无法覆盖完整硬门槛窗口
- **THEN** 实验产物 MUST 标记 `formal_eligible = false`
- **THEN** 实验产物 MUST 记录 `reject_reason = short_history`
- **THEN** 系统仍可在其上市后的重叠窗口中输出 shadow diagnostics

### Requirement: promotion from shadow pool to formal pool MUST require a new formal pool version
任何 shadow ETF 转入正式主线 MUST 通过新的 formal pool version 和独立 OpenSpec change 表达。系统 SHALL NOT 通过修改 shadow preset、study yaml 或 audit 展示字段来完成正式转入。

#### Scenario: candidate passes shadow diagnostics
- **WHEN** shadow 候选在三窗口研究中表现可接受
- **THEN** 当前 change 的输出只能给出 promotion recommendation
- **THEN** 系统 MUST 保持 `formal_etf_pool_v1` 不变
- **THEN** 正式纳入 MUST 等待新的 `formal_etf_pool_vN` change
