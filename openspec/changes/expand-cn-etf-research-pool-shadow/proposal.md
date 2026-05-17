## Why

当前正式 ETF 池偏窄，主要覆盖大盘、中盘、小盘与单一债券防守，缺少红利、黄金、成长风格和科创成长等可解释的分散暴露。ETF 扩池属于 L3 资产池改动，不能直接进入 `CN_STOCK_ETF_FORMAL_V1`，需要先建立 research-only shadow 池、三窗口验证和 promotion 门槛。

## What Changes

- 新增 `cn_etf_research_shadow_pool_v1` 研究池版本，只用于 shadow experiment，不改变 `formal_etf_pool_v1`、baseline truth、成交时点、信号时点或组合构建主逻辑。
- 将已在本地 catalog / 数据层可支持的候选分层纳入 shadow 研究：
  - `510880.SH` 红利ETF：优先研究的价值/分红风格候选。
  - `518880.SH` 黄金ETF：防守/多资产分散候选，不直接作为 core beta。
  - `159915.SZ` 创业板ETF：成长风格候选。
  - `588000.SH` 科创50ETF：科技成长候选，仅 shadow，因历史窗口较短需要单独标注。
  - `512890.SH` 红利低波ETF：与 `510880.SH` 做角色重叠对照。
  - `159845.SZ` 中证1000ETF：作为 `512100.SH` 的标准化替代候选，而不是新增小盘暴露。
- 明确暂不纳入本轮实验的候选：
  - `511880.SH`、`511260.SH`：现金/久期层候选，需另案定义防守层和现金等价物会计语义。
  - `513500.SH`、`513100.SH` 等跨境 ETF：涉及 QDII 溢价、汇率和交易日历，另案研究。
  - 行业/主题 ETF：本轮不纳入，避免把 ETF sleeve 变成主题轮动引擎。
- 增加 shadow 池输出与审计要求：实验产物必须标明 pool version、symbol role、coverage window、formal eligibility、promotion gate 结论和未通过原因。
- **BREAKING**: 无。该 change 只增加 research-only shadow 合同，不修改当前正式 ETF 池。

## Capabilities

### New Capabilities
- `cn-etf-research-shadow-pool`: 定义版本化 ETF research-only shadow 池、候选角色、暂缓范围、三窗口验证与转正式门槛。

### Modified Capabilities
- `cn-etf-research-entry`: 增加受控 shadow pool preset / catalog classification 输出，使研究入口能显式区分 formal、shadow 和 deferred 标的。
- `cn-etf-beta-sleeve`: 强化正式 ETF sleeve 与 shadow 池隔离要求，防止 shadow 标的被静默升级为正式可交易池。

## Impact

- 影响主路径预期包括：
  - `backend/core/data/cn_etf_catalog.py`
  - `backend/core/universe/universe_resolver.py`
  - `backend/core/config/etf_beta/defaults.py`
  - `backend/core/config/etf_beta/summary.py`
  - `backend/core/audit/research_audit.py`
  - `research/studies/etf/*`
  - `tests/unit/test_cn_etf_catalog.py`
  - `tests/unit/test_universe_resolver.py`
  - `tests/unit/test_etf_beta_contract.py`
  - `tests/unit/test_research_audit_contract.py`
- 不影响：
  - 当前 live baseline `CN_STOCK_ETF_FORMAL_V1`
  - `formal_etf_pool_v1`
  - 股票 alpha sleeve
  - 账户层预算分配
  - ETF 分红现金流新口径
  - `outputs/` 作为运行产物的边界
