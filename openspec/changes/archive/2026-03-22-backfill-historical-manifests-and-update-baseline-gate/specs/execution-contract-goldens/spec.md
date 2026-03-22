## ADDED Requirements

### Requirement: baseline gate 必须锚定当前正式基线并区分行为漂移与批准结构升级
系统 MUST 让 baseline regression gate 锚定当前正式基线 `baseline_V10.1 -> exp_20260314_144548534_7db9`。gate MUST 继续把 `perf`、`nav`、`portfolio_trades`、`portfolio_candidates` 和 manifest 关键语义作为阻塞型行为门，同时 MUST 将已批准的 schema enrichment 与行为漂移区分处理。

#### Scenario: 运行当前正式基线对照
- **WHEN** 系统执行默认 baseline regression compare
- **THEN** gate MUST 默认以 `exp_20260314_144548534_7db9` 作为正式锚点
- **THEN** 对照结果 MUST 继续保护 `V10.1` 的收益、回撤、交易数和核心语义不漂移

#### Scenario: 已批准的 schema enrichment 不再被误判为行为失败
- **WHEN** 对照结果仅出现已批准的结构升级，例如 canonical `asset_scope`、canonical `asset_context` 或因 approved config schema 扩展导致的 `run_config_hash` 变化
- **THEN** gate MUST 通过 contract 规则显式识别并处理这些差异
- **THEN** 系统 SHALL NOT 将其继续报告为阻塞型行为漂移

### Requirement: enriched daily artifact gate 必须从整文件哈希门转为语义门
当 `portfolio_daily.csv` 因诊断字段、canonical 字段或 approved schema enrichment 新增列时，baseline gate MUST 使用稳定的语义摘要门，而 SHALL NOT 继续把整文件哈希视为唯一阻塞门。

#### Scenario: daily artifact 新增诊断列
- **WHEN** `portfolio_daily.csv` 仅新增已批准的诊断列或 canonical 元数据列
- **THEN** gate MUST 比较稳定语义摘要，例如行数、日期范围和关键聚合摘要
- **THEN** 该类列扩展 SHALL NOT 单独导致阻塞失败

#### Scenario: daily artifact 核心语义漂移
- **WHEN** `portfolio_daily.csv` 的关键行数、日期范围或关键聚合摘要发生非预期变化
- **THEN** gate MUST 将该变化判定为阻塞型失败
- **THEN** 结构优化不得作为接受该漂移的理由
