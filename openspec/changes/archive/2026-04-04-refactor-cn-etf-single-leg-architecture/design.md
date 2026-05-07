## Context

当前 ETF 单腿主链的正式实现被长期压在少数热点文件里：

- `backend/core/config/etf_beta_contract.py` 同时承担常量、默认值、归一化、暴露语义、summary builder。
- `backend/core/engine_vector/cn_etf_beta_signal_provider.py` 同时承担配置翻译、候选池解析、排序、执行路径、诊断聚合。
- `backend/core/stage_pipeline/adapters/daily_accounting.py` 同时承担通用记账和 ETF actual exposure / gap / formal-research view 解释。
- `backend/api/backtest_v2/artifacts_finalize.py` 仍然需要知道 ETF summary 的拼装细节。

这种结构的直接问题不是“文件太长”本身，而是 ETF 单腿的四层真相被混在一起了：

1. 规则与合同真相
2. 执行与下单路径
3. 日级审计与 target/actual 解释
4. summary / run_meta 固化

当前结果又已经暴露出 ETF 单腿存在明显的低暴露问题，因此这轮必须先把架构拆清，保证后续分析瓶颈时能准确定位到底是合同、执行、节奏还是审计口径的问题。

本次 change 的约束也很明确：

- 只处理 ETF 单腿
- 不扩展到 stock+ETF combo
- 不扩展到前端
- 不把研究语义改造、池子扩容或收益优化混入同一轮 change
- 需要保留现有入口，避免一次性打爆 import 与调用链

## Goals / Non-Goals

**Goals:**

- 将 ETF 单腿实现拆成清晰的四层边界：规则/配置、执行、审计、summary。
- 保留现有稳定入口，使 `etf_beta_contract.py` 和 `cn_etf_beta_signal_provider.py` 在第一轮仍可作为 facade 使用。
- 参考 A 股个股子系统“治理配置层与执行层分离”的思路，但不机械复制目录。
- 让 `daily_accounting.py` 和 `artifacts_finalize.py` 只承担编排职责，不再继续沉淀 ETF 专属热点逻辑。
- 为后续定位 ETF 低暴露、deployment pace、rebalance timing 等瓶颈准备清晰边界。

**Non-Goals:**

- 不修改 stock+ETF unified combo 语义与 runtime。
- 不修改前端加载链路与展示结构。
- 不在本轮内扩 ETF 池、修改 study 研究边界或引入新的策略角色。
- 不承诺本轮直接提升 CAGR 或修复所有行为问题。
- 不追求一步到位的“大搬家”，避免引入高风险导入震荡。

## Decisions

### 1. 采用“薄 facade + 内部子模块”迁移，而不是一次性整体搬家

决策：

- 保留 `backend/core/config/etf_beta_contract.py` 作为稳定 facade。
- 保留 `backend/core/engine_vector/cn_etf_beta_signal_provider.py` 作为稳定 facade。
- 内部实现迁移到 ETF 专属子模块目录。

原因：

- 这是当前风险最低的迁移路径。
- 可以优先把职责拆开，而不要求所有调用点同轮改 import。
- 回退成本低，出现回归时只需要回退局部提取模块。

备选方案：

- 直接整体迁移到新的 `backend/core/etf/` 根目录。

不采纳原因：

- 一次性 import 迁移面太大。
- 与 combo、artifact、tests 的连接点太多，首轮不利于控风险。

### 2. 合同层按“默认值 / 归一化 / 暴露语义 / summary”四块拆分

目标目录：

```text
backend/core/config/etf_beta/
  __init__.py
  defaults.py
  normalization.py
  exposure_semantics.py
  summary.py
```

决策：

- `defaults.py` 负责常量、默认 contract 和角色/边界默认值。
- `normalization.py` 负责 governed `etf_beta` 配置清洗与归一化。
- `exposure_semantics.py` 负责 target exposure、bucket、deployment pace、formal/research 语义求解。
- `summary.py` 负责 phase1 summary 与对外摘要结构。

原因：

- 这四类逻辑修改频率和依赖方向不同，不应再长期混在一起。
- `normalize` 与 `resolve` 混在一起时，任何行为排查都很难确认是输入清洗还是合同解释的问题。
- `summary` 是消费层语义，不应反向污染合同主逻辑。

备选方案：

- 继续保留单文件，只抽少量 helper。

不采纳原因：

- 这只能缩短函数，不会解决职责边界问题。

### 3. Provider 层按“配置装配 / 候选池与排序 / 执行路径 / 诊断聚合”拆分

目标目录：

```text
backend/core/engine_vector/etf_beta/
  __init__.py
  provider_config.py
  provider_state.py
  candidate_pool.py
  selection.py
  execution_paths.py
  diagnostics.py
```

决策：

- 先建立 `provider_state.py` 或等价 state owner，统一托管 provider 的 ndarray / cache / 日级状态。
- `provider_config.py` 负责把 semantic config 翻译为 ETF provider 可执行配置。
- `candidate_pool.py` 与 `selection.py` 负责池子解析、候选排序、target selection。
- `execution_paths.py` 负责 monthly rebalance、`TRANS_UP` redeploy 等执行路径。
- `diagnostics.py` 负责 reason code、target/actual gap、执行路径标签等诊断聚合。

原因：

- 当前 provider 最大的问题不是函数太长，而是状态、决策、诊断三者混在一起。
- 没有 state owner，就会继续依赖大量分散在 `self` 上的隐式字段，拆分后仍然难维护。
- 执行路径和诊断路径必须分离，否则解释代码会反向污染下单代码。

备选方案：

- 按 method 机械切成多个 helper 文件。

不采纳原因：

- 如果不先定义 state/config owner，helper 只会把耦合换个位置继续存在。

### 4. ETF actual exposure 与 formal/research view 建立专属 accounting 边界

目标文件：

```text
backend/core/stage_pipeline/adapters/etf_beta_accounting.py
```

决策：

- 将 ETF actual exposure、policy/timing/residual gap、formal/research view 组装迁出 `daily_accounting.py`。
- `daily_accounting.py` 只负责调度与写入共享日级结构。

原因：

- ETF 的 target/actual 解释已经是专属领域逻辑，不应继续压在通用记账热点里。
- 这层边界清楚后，后续才能单独验证“低暴露到底来自合同、节奏还是执行残差”。

备选方案：

- 继续在 `daily_accounting.py` 内部增加 ETF helper。

不采纳原因：

- 通用 adapter 会继续变长，热点不会真正消失。

### 5. `artifacts_finalize.py` 继续做 orchestrator，不拥有 ETF summary 真相

决策：

- ETF phase1 summary 的拼装真相保留在 ETF summary 模块。
- `artifacts_finalize.py` 只消费稳定 summary API，把结果写入 `run_meta` 与 `governed_snapshot`。

原因：

- artifact 固化层是消费层，不应重新拥有 ETF 合同解释权。
- 这样可以避免 summary contract 漂移成 API 私有逻辑。

备选方案：

- 在 `artifacts_finalize.py` 直接重写 ETF summary 拼装。

不采纳原因：

- 会形成第二份 ETF 真相。

### 6. 参考 A 股个股子系统的“分层思想”，不做一比一仿制

决策：

- 借鉴个股子系统“治理配置层 / 执行层”分离的方向。
- 不强行把 ETF 文件命名、对象模型做成个股子系统的镜像。

原因：

- ETF 单腿与个股 alpha 子系统的对象模型不同。
- 需要复用的是边界纪律，而不是目录表面相似性。

## Risks / Trade-offs

- [导入兼容风险] → 保留 facade，第一轮不要求外部调用点改 import，并用现有 ETF contract/provider 测试回归。
- [隐式 state 迁移出错] → 先定义 state owner，再拆执行路径；禁止边拆边继续新增 `self._etf_beta_*` 隐式字段。
- [审计口径漂移] → ETF accounting helper 与 artifacts finalize 只允许单向消费同一份 summary / semantics API，避免双重重算。
- [scope creep] → 本次 change 明确排除 combo、前端、study 语义扩展，任务清单只围绕 ETF 单腿主链。
- [短期重复代码] → 允许过渡期 facade re-export 和薄包装存在，但 apply 完成后必须把旧热点收薄，而不是形成两份长期实现。
- [循环依赖] → 依赖方向固定为 `config -> engine_vector -> stage_pipeline/adapters -> api/artifacts`，禁止反向引用。

## Migration Plan

1. 新建 ETF contract 子目录，并将默认值、归一化、暴露语义、summary 逐步迁出旧文件。
2. 将 `etf_beta_contract.py` 收薄为 facade/re-export，保留旧入口函数名。
3. 新建 ETF provider 子目录，先建立 config/state owner，再迁移候选池、选择、执行路径、诊断聚合。
4. 将 `cn_etf_beta_signal_provider.py` 收薄为 facade，保留 `CNETFBetaSignalProvider` 对外入口。
5. 新建 `etf_beta_accounting.py`，把 ETF actual exposure 与 formal/research view 组装迁出 `daily_accounting.py`。
6. 保持 `artifacts_finalize.py` 通过稳定 summary API 固化现有 artifact 字段，不把 ETF 细节重新塞回 API 层。
7. 用现有 ETF contract/provider/accounting/artifact 相关测试回归，确认旧入口仍可用。

回退策略：

- 若 contract 层回归，直接回退 `backend/core/config/etf_beta/` 与 `etf_beta_contract.py` 的 facade 改动。
- 若 provider 层回归，直接回退 `backend/core/engine_vector/etf_beta/` 与 `cn_etf_beta_signal_provider.py` 的 facade 改动。
- 若 accounting / artifact 层回归，回退 `etf_beta_accounting.py` 与两处调用点即可。

## Open Questions

- 无阻塞问题。本次命名和模块粒度按“最小可迁移单元”执行；若 apply 阶段发现单个子模块仍然过大，再在同一目录内继续细分，而不新增更高层目录。
