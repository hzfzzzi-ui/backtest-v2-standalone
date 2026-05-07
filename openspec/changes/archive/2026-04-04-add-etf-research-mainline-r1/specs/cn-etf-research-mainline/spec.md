## ADDED Requirements

### Requirement: 系统 MUST 提供 research-only 的 ETF 独立收益主线 R1
系统 MUST 提供一条名为 `etf/cn_broad_based_research_mainline_r1` 的 research-only ETF 主线 study。该主线 MUST 明确被标记为独立收益研究线，而不是 formal `cn-etf-beta-sleeve` 或 stock+ETF combo 的正式锚点。

#### Scenario: 研究入口装载 R1 主线
- **WHEN** 用户加载 `etf/cn_broad_based_research_mainline_r1`
- **THEN** 系统 MUST 将其识别为 `research-only` 的 ETF 独立收益主线
- **THEN** 系统 SHALL NOT 将其解释为 formal ETF sleeve 或 baseline 正式锚点

### Requirement: R1 主线 MUST 使用受控目录内的 A股核心承接 + 固定科创成长席位 + 双防守层
R1 主线 MUST 仅使用当前 `cn_etf` 受控 research entry 已覆盖的 ETF，并按以下角色分层：

- A股核心承接：`510050.SH`、`510300.SH`、`510500.SH`、`512100.SH`、`512890.SH`
- 固定成长席位：`588000.SH`
- 防守层：`511010.SH`、`518880.SH`

R1 主线 SHALL NOT 同时启用 `159915.SZ` 作为并列 growth seat。

#### Scenario: R1 主线加载资产角色
- **WHEN** 系统物化 R1 主线的 study 配置
- **THEN** `588000.SH` MUST 被标记为唯一 growth seat
- **THEN** `511010.SH` 与 `518880.SH` MUST 只作为防守层而不作为风险开时的进攻排名成员

### Requirement: R1 主线 MUST 采用双周 `core_growth_slot` 选择结构
R1 主线 MUST 使用 `core_growth_slot` 作为选择链，并使用 `biweekly` 调仓频率。强状态下系统 MUST 允许 `core + growth` 双席位；弱状态下，当 `target_selected_count=1` 时，系统 MUST 只保留 core slot。

#### Scenario: 强状态允许双席位
- **WHEN** R1 主线处于 `BULL` 或 `TRANS_UP`，且 `target_selected_count >= 2`
- **THEN** 系统 MUST 允许同时选择 `core slot` 与 `growth slot`
- **THEN** `growth slot` MUST 只来自 `588000.SH`

#### Scenario: 弱状态压掉 growth slot
- **WHEN** R1 主线处于 `TRANS_DOWN` 或 `RISK_OFF`，且 `target_selected_count = 1`
- **THEN** 系统 MUST 只保留 `core slot`
- **THEN** 系统 SHALL NOT 在该状态下把 `588000.SH` 作为唯一 live seat

### Requirement: R1 主线 MUST 支持弱市核心承接与双防守共存
R1 主线 MUST 允许 `LIGHT`、`TRANS_DOWN` 与 `RISK_OFF` 继续保留正的 A股核心承接预算，但 `RISK_OFF` 的 live 风险暴露 MUST 被限制为单一 core seat。系统同时 MUST 支持 `511010.SH + 518880.SH` 双防守层，以及以 `511010.SH` 作为单 symbol fallback。

#### Scenario: RISK_OFF 仍保留小幅核心承接
- **WHEN** R1 主线处于 `RISK_OFF`
- **THEN** 系统 MUST 允许存在正的 `target_exposure`
- **THEN** 该正预算 MUST 只对应单一 core seat，而不是成长席位或双风险席位

#### Scenario: 双防守层与 fallback 并存
- **WHEN** R1 主线进入弱状态并需要防守层
- **THEN** 系统 MUST 支持同时配置 `limited_defense_candidates=[511010.SH, 518880.SH]`
- **THEN** 系统 MUST 继续允许 `fallback_mode=single_symbol` 且 `fallback_symbol=511010.SH`
