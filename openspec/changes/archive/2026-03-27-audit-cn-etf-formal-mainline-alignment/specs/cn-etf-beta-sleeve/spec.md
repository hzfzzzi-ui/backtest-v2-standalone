## MODIFIED Requirements

### Requirement: ETF beta sleeve 的 Phase 1 范围必须受控
Phase 1 中，`cn-etf-beta-sleeve` MUST 仅将以下 ETF 视为正式 core beta 范围：
- `510300.SH`
- `510500.SH`
- `510050.SH`
- `512100.SH`

Phase 1 MAY 允许 `512890.SH` 作为 limited defense candidate，但 SHALL NOT 将 `518880.SH`、`511010.SH`、`588000.SH`、`159915.SZ` 并入正式 core beta sleeve。

系统 MUST 区分“正式主线运行路径”和“研究分支运行路径”：
- 只有符合上述 Phase 1 范围的路径，才可以被标记为 `formal_mainline`
- 超出范围的 ETF 路径 MAY 继续存在于研究目录中，但 MUST 被显式标记为 `research_only` 或 `do_not_promote`

#### Scenario: 正式 core beta 资产受控
- **WHEN** 系统构建 `cn_etf_beta` 的正式 Phase 1 候选池
- **THEN** 候选池 MUST 至少受限于四只 core beta ETF
- **THEN** `512890.SH` MAY 在 Governor 或策略配置允许时作为 limited defense candidate

#### Scenario: 非 Phase 1 范围 ETF 不得被伪装成正式 core beta
- **WHEN** 研究入口包含 `518880.SH`、`511010.SH`、`588000.SH` 或 `159915.SZ`
- **THEN** 系统 SHALL 将其标记为超出 `cn_etf_beta` Phase 1 正式范围
- **THEN** 系统 SHALL NOT 把这些资产静默纳入正式 beta sleeve 真相

#### Scenario: 超范围研究路径必须显式降级
- **WHEN** 某条 ETF runtime profile 或 study 使用正式文档之外的资产作为正式主线核心组成
- **THEN** 系统 MUST 将该路径分类为 `research_only` 或 `do_not_promote`
- **THEN** 系统 MUST 暴露显式偏离原因
