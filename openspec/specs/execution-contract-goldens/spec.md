# execution-contract-goldens Specification

## Purpose
Synced from delta spec during archive. The capability contract is now part of the main spec set.
## Requirements
### Requirement: 执行链必须通过显式 contract 交接核心状态
系统 MUST 使用显式 `RuntimePlan`、`ExecutionIntent` 和 `AccountingSnapshot` 契约在执行链关键阶段交接核心状态。`order_planning`、`fill_accounting` 和 `daily_accounting` SHALL NOT 再通过隐式 dict 字段传递核心状态。

#### Scenario: 信号进入订单规划
- **WHEN** 执行链从信号阶段进入订单规划
- **THEN** 系统 MUST 使用 `ExecutionIntent` 交接买卖候选、风险标记和排序载荷
- **THEN** 下游 SHALL NOT 依赖未声明的隐式字段

#### Scenario: 成交后进入日终记账
- **WHEN** 系统完成 fill 并进入日终记账
- **THEN** 系统 MUST 使用 `AccountingSnapshot` 交接现金、持仓、filled orders、trade rows 和 counters
- **THEN** NAV、daily rows 和 metrics SHALL 从该显式快照推导

### Requirement: 主循环替换前必须有最小覆盖集 goldens
系统 MUST 在正式替换主循环前建立最小覆盖集 goldens。最小覆盖集 MUST 至少包含 `baseline_V10`、一个 locked candidate preset、一个 representative generic route 和一个 representative breakout route。

#### Scenario: golden 覆盖集准备完成
- **WHEN** 系统准备替换 strict 或 legacy 主流程
- **THEN** 每个覆盖样本 MUST 具有固定输入和可比输出
- **THEN** 覆盖项 MUST 至少包含 `orders`、`trades`、`NAV`、`perf` 和 `counters`

#### Scenario: golden 不完整时尝试替换主循环
- **WHEN** 某个覆盖样本缺少必要 golden
- **THEN** 系统 SHALL NOT 进入正式主循环替换
- **THEN** 该重构任务 MUST 先补齐 golden

### Requirement: 时间可得性审计必须覆盖敏感模块迁移
系统 MUST 对 rolling、rank、zscore、市场状态、财务和行业快照等敏感模块迁移执行单独的时间可得性审计。任何导致 10.1 价格型信号口径漂移的迁移 SHALL 被判定为失败。

#### Scenario: 迁移 rolling 或 rank 模块
- **WHEN** 系统迁移 rolling、rank 或 zscore 相关模块
- **THEN** 系统 MUST 单独验证窗口只使用历史可得样本
- **THEN** 审计结果 MUST 能说明未引入未来函数或时点错位

#### Scenario: 价格型信号结果出现偏移
- **WHEN** 迁移后 `orders`、`trades`、`NAV`、`perf` 或 `counters` 与黄金样本发生非预期偏移
- **THEN** 系统 MUST 将该迁移判定为失败
- **THEN** 不得以结构优化为理由接受该偏移

### Requirement: execution contract goldens 必须覆盖 lineage id 与生命周期终态
系统 MUST 在执行链 golden 覆盖集中加入 lineage 相关断言，至少校验代表性样本的 `signal_id`、`order_id`、`fill_id` 传播关系和生命周期终态。

系统 MUST 在执行链 golden 覆盖集中加入 lineage 相关断言，至少校验代表性样本的 `signal_id`、`order_id`、`fill_id` 传播关系和生命周期终态。

#### Scenario: golden 校验稳定 lineage id
- **WHEN** 代表性路由执行 golden 测试
- **THEN** golden 结果 SHALL 能校验 `signal_id -> order_id -> fill_id` 的父子关系
- **THEN** 相同输入下 lineage id SHALL 保持稳定

#### Scenario: golden 校验生命周期终态
- **WHEN** golden 样本包含成交、取消、拒绝或失效等路径
- **THEN** golden 结果 SHALL 能校验对应终态与原因字段
- **THEN** 任一非预期状态漂移 SHALL 被判定为 contract 失败### Requirement: baseline gate 必须锚定当前正式基线并区分行为漂移与批准结构升级
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

当 `portfolio_daily.csv` 因诊断字段、canonical 字段或 approved schema enrichment 新增列时，baseline gate MUST 使用稳定的语义摘要门，而 SHALL NOT 继续把整文件哈希视为唯一阻塞门。

#### Scenario: daily artifact 新增诊断列
- **WHEN** `portfolio_daily.csv` 仅新增已批准的诊断列或 canonical 元数据列
- **THEN** gate MUST 比较稳定语义摘要，例如行数、日期范围和关键聚合摘要
- **THEN** 该类列扩展 SHALL NOT 单独导致阻塞失败

#### Scenario: daily artifact 核心语义漂移
- **WHEN** `portfolio_daily.csv` 的关键行数、日期范围或关键聚合摘要发生非预期变化
- **THEN** gate MUST 将该变化判定为阻塞型失败
- **THEN** 结构优化不得作为接受该漂移的理由### Requirement: baseline gate 必须锚定当前正式基线并区分行为漂移与批准结构升级
系统 MUST 让 baseline regression gate 锚定当前正式基线 `baseline_V10.1 -> exp_20260314_144548534_7db9`。gate MUST 继续把 `perf`、`nav`、`portfolio_trades`、`portfolio_candidates` 和 manifest 关键语义作为阻塞型行为门，同时 MUST 将已批准的 schema enrichment 与行为漂移区分处理。

#### Scenario: 运行当前正式基线对照
- **WHEN** 系统执行默认 baseline regression compare
- **THEN** gate MUST 默认以 `exp_20260314_144548534_7db9` 作为正式锚点
- **THEN** 对照结果 MUST 继续保护 `V10.1` 的收益、回撤、交易数和核心语义不漂移

#### Scenario: 已批准的 schema enrichment 不再被误判为行为失败
- **WHEN** 对照结果仅出现已批准的结构升级，例如 canonical `asset_scope`、canonical `asset_context` 或因 approved config schema 扩展导致的 `run_config_hash` 变化
- **THEN** gate MUST 通过 contract 规则显式识别并处理这些差异
- **THEN** 系统 SHALL NOT 将其继续报告为阻塞型行为漂移

