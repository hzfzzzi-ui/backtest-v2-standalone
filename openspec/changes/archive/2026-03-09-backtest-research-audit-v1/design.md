## Context

当前系统已经存在三类审计相关能力，但它们没有形成统一的 research audit 结论层：

- 实验产物审计：由 `foundation_shell` 与 `backtest_v2_artifacts` 生成 `stage_summary.json`、`audit.json`、`manifest.json`，稳定进入主实验链路。
- 数据校验审计：由 `/api/backtest_v2/validate_data` 和 `validate_pg.py` 生成 `validate_data.json`，用于独立检查源数据质量，但并不自动绑定到实验目录。
- 底层查询/旧式审计：`pg_provider.query_audit` 与 `engine_vector.AuditCollector` 存在，但当前不属于主实验链路的稳定消费能力。

现状的核心问题不是“没有审计文件”，而是“没有统一 verdict”。`audit.json` 目前主要记录 execution shell、stage 顺序和少量统计，能够说明“怎么跑的”，但不能统一说明“结果是否可信”。这在研究流程里会直接导致候选比较与晋级标准漂移。

## Goals / Non-Goals

**Goals:**
- 为每次实验在现有 `audit.json` 中生成唯一的 `research_audit` verdict。
- 复用已有产物和字段，不新增新的 metadata 文件，不重复存储 `run_meta`、`stage_summary`、`manifest` 中已有内容。
- 用五个 gate 统一判断：`timing_alignment`、`universe_lineage`、`execution_realism`、`reproducibility`、`result_sanity`。
- 在不改 baseline 研究口径的前提下，优先解决“统一收口 + 实验可信度判断”。
- 对当前实验链路最小入侵，保持 `foundation_shell -> ensure_standard_artifacts -> stabilize_experiment_result` 的主干不变，只在 artifact stabilize 收尾阶段追加 research verdict 写盘。

**Non-Goals:**
- 不做完整未来函数检测，不试图在 v1 中证明所有信号输入都 PIT-safe。
- 不重写 `engine_vector.AuditCollector` 或把 `query_audit` 改造成主链路依赖。
- 不新增 `research_audit.json` 之类的第二份总账文件。
- 不强制 `validate_data` 成为每次实验运行的前置步骤。
- 不大改 `report_generator` 的报表结构；如需展示 research audit，只允许追加轻量只读区块。

## Decisions

### D1: 采用“双层审计、单文件收口”模型

`audit.json` 保持为唯一审计总账，但内部职责拆成两层：

- 现有 execution audit trail：保留 `summary/flags/stage_pipeline/warnings` 等执行与数据质量审计内容。
- 新的 `research_audit`：只负责实验可信度 verdict，不重复保存已有原始元数据。

选择理由：
- 兼容现有 `backtest-audit` 能力，避免再造新产物。
- 用户的研究问题是“这个结果能不能信”，更适合独立 verdict 子树，而不是继续往 execution summary 里堆字段。

拒绝的备选方案：
- 新增 `research_audit.json`
  - 拒绝，因为会制造第二份实验总账，破坏当前 `audit.json` 的收口位置。
- 直接把五个 gate 混入 `run_meta.json`
  - 拒绝，因为 `run_meta` 是元信息快照，不适合承载 verdict 和证据引用。

### D2: `backtest_v2_artifacts.stabilize_experiment_result()` 是唯一 research audit 写入口

`research_audit` 的生成与写盘统一放在 [backtest_v2_artifacts.py](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/api/endpoints/backtest_v2_artifacts.py)。

职责分工：
- `foundation_shell` 继续只产出 stage 相关原始证据。
- `experiment_runner` 继续只透传 `metrics/stage_summary/stage_pipeline`。
- `ensure_standard_artifacts()` 继续负责基础 artifact 标准化与落盘。
- `stabilize_experiment_result()` 在 `manifest.json` 已生成后调用 `_finalize_research_audit(...)`，统一生成 `research_audit` 并回写 `audit.json`。

选择理由：
- 当前这里已经掌握 `result`、`results_dir`、`artifacts`、`run_meta` 组装上下文，是证据最完整的收口点。
- 可以确保 `audit.json`、`run_meta.json`、`stage_summary.json`、`manifest.json` 口径来自同一处。

拒绝的备选方案：
- 在 `foundation_shell` 中直接生成 research verdict
  - 拒绝，因为它看不到 manifest/config snapshots/perf/trades 等完整证据。
- 在报表生成阶段反向推导
  - 拒绝，因为报表不是实验真相源，而且会把审计逻辑绑到展示层。

### D3: 新增独立的 research audit 构建模块

新增一个轻量模块，例如 `backend/core/audit/research_audit.py`，内部职责拆分为：

- `collect_research_evidence(...)`
- `evaluate_timing_alignment(...)`
- `evaluate_universe_lineage(...)`
- `evaluate_execution_realism(...)`
- `evaluate_reproducibility(...)`
- `evaluate_result_sanity(...)`
- `aggregate_overall_status(...)`
- `build_research_audit(...)`

输出结构固定为：

```json
{
  "contract_version": "research_audit@1",
  "overall_status": "PASS|WARN|FAIL|UNKNOWN",
  "gates": {
    "timing_alignment": {},
    "universe_lineage": {},
    "execution_realism": {},
    "reproducibility": {},
    "result_sanity": {}
  },
  "evidence_refs": {
    "run_meta": "run_meta.json",
    "manifest": "manifest.json",
    "stage_summary": "stage_summary.json",
    "trades": "portfolio_trades.csv",
    "symbol_performance": "symbol_performance.csv",
    "validate_data": null
  }
}
```

选择理由：
- 研究 verdict 与 stage 归一化是不同职责，继续塞进 `experiment_audit.py` 会让 contract 混杂。
- 五个 gate 彼此独立，分函数实现更利于后续扩展与验证。

### D4: 证据只引用，不复制

`research_audit` 只保存：

- `status`
- `reason`
- `metrics`
- `evidence`
- `evidence_refs`

明确不做：
- 复制 `run_meta.universe`
- 复制 `stage_summary`
- 复制完整 `validate_data` payload

`evidence_refs.validate_data` 的最小形态为：

```json
{
  "request_id": "val_xxx",
  "path": "outputs/val_xxx/audit/validate_data.json",
  "pass": true,
  "warning_codes": ["LOW_COVERAGE_WARNING"]
}
```

若本次实验没有可追溯的 validate evidence，则写 `null`。

选择理由：
- 满足“不重复定义已有产物”的要求。
- 让 `audit.json` 保持紧凑且可机器解析。

### D5: 五个 gate 的证据来源固定如下

```text
timing_alignment
  -> stage_summary / stage_pipeline / execution shell metadata

universe_lineage
  -> run_meta.universe + backend.core.universe.lineage policy + resolve_asof/dynamic_all_a_entry

execution_realism
  -> portfolio_trades.csv + traded-symbol/day bar reload + optional audit warnings

reproducibility
  -> artifacts + config_snapshots + report_consistency + resolved_config_hash

result_sanity
  -> perf.json + run_meta.counters + symbol_performance.csv
```

选择理由：
- 每个 gate 都尽量复用现有 artifact，新增计算只集中在 `execution_realism`。

### D6: `overall_status` 采用严格聚合规则

聚合顺序固定：

1. 任一 gate = `FAIL` -> `overall_status = FAIL`
2. 无 `FAIL`，但存在 `WARN` -> `overall_status = WARN`
3. 无 `FAIL/WARN`，但存在 `UNKNOWN` -> `overall_status = UNKNOWN`
4. 全部 `PASS` -> `overall_status = PASS`

选择理由：
- 与用户给定的 v1 contract 一致。
- 研究审计必须保守，尤其在 timing 证明不足时不能误给 PASS。

### D7: `timing_alignment` 默认保守，不轻易 PASS

v1 的 `timing_alignment` 只承诺检查执行壳契约，不承诺完整证明特征 PIT 安全。

判定规则：
- 明确发现同日收盘信号并同日收盘成交 -> `FAIL`
- 明确发现未来财务数据或未来成分股被用于信号 -> `FAIL`
- execution shell 明确 next-day，但无法证明信号输入 PIT 安全 -> `UNKNOWN`
- execution shell 元信息冲突或壳行为不一致 -> `WARN`
- 同时证明 next-day execution 和输入 PIT 安全 -> `PASS`

选择理由：
- 当前代码最稳能证明的是 stage shell 的 next-trading-day contract。
- 不把“无法证明安全”误判为“安全”。

### D8: `universe_lineage` 采用四种标准模式

标准模式：

- `PIT_DYNAMIC`
- `START_SNAPSHOT`
- `CURRENT_SNAPSHOT`
- `UNKNOWN`

状态映射：

- `PIT_DYNAMIC` -> `PASS`
- `START_SNAPSHOT` -> `WARN`
- `CURRENT_SNAPSHOT` -> `FAIL`
- `UNKNOWN` -> `UNKNOWN`

当前代码下的默认映射：

- `ALL_A` -> `CURRENT_SNAPSHOT`
  - 原因：当前 resolver 以 `end_date` 的 active CN_A 作为全集，再做 `dynamic_daily_gate`；这不是严格的历史时点动态成分。
- `HS300_ZZ500` -> `START_SNAPSHOT`
- `CSI1000` -> `START_SNAPSHOT`
- `INDUSTRY` -> `START_SNAPSHOT`
- `CUSTOM` -> `UNKNOWN`

选择理由：
- 这四类已经足够覆盖当前系统的研究口径差异。
- `ALL_A` 的 current-snapshot 风险必须显式暴露，不能因名字看似“动态”而误判。

### D9: `execution_realism` 是 v1 唯一新增的实验级计算

实现方式：
- 从 `portfolio_trades.csv` 取实际成交的 `(symbol, date)`。
- 使用现有 runtime data access 边界按成交 symbols 和实验区间回查最小必要的日线 bar。
- 逐笔判断：
  - 停牌成交
  - 缺 bar 成交
  - 零成交量成交
  - 零成交额成交
  - 涨停买入
  - 跌停卖出

阈值规则：
- `停牌成交 / 缺 bar 成交 / 零成交量成交 / 零成交额成交` 任一出现 -> `FAIL`
- `涨停买入 / 跌停卖出` 占总成交笔数 `> 1%` -> `FAIL`
- `涨停买入 / 跌停卖出` 占总成交笔数 `> 0` 且 `<= 1%` -> `WARN`
- 无交易或无法核对 -> `UNKNOWN`
- 其余 -> `PASS`

选择理由：
- 这是最常见、最可落地、最能提升研究可信度的失真来源检查。
- 通过 runtime data access 回查少量 bars，比重写引擎埋点更小。

拒绝的备选方案：
- 完全依赖 `validate_data`
  - 拒绝，因为 `validate_data` 检的是源表质量，不是“这笔成交是否真实可成交”。
- 把 `execution_realism` 留到 v2
  - 拒绝，因为它是 v1 最值得补的空缺。

### D10: `reproducibility` 对新实验严格，对历史实验不追溯惩罚

对 v1 新生成实验：
- 缺 `run_meta.json`、`manifest.json`、`audit.json` -> `FAIL`
- 核心产物齐全，但 config snapshots 不全 -> `WARN`
- `config_snapshots` 与 `resolved_config_hash` 可追溯 -> `PASS`

对历史实验：
- 本 change 不做回填，不 retroactive 改写旧实验目录。
- 缺失 `research_audit` 的旧目录不自动判定为失败，只是“未升级到新 contract”。

选择理由：
- 避免把历史 schema 差异误判成研究失败。
- 对新实验维持可复现门槛。

### D11: `result_sanity` 只做异常检测，不做策略评价

v1 指标来源：
- `perf.json`
- `run_meta.counters`
- `symbol_performance.csv`

默认阈值：
- `Sharpe > 5` -> `FAIL`
- `CAGR > 100%` -> `FAIL`
- `Sharpe > 3` -> `WARN`
- `CAGR > 50%` -> `WARN`
- 利润过度集中 -> `WARN`
- 指标缺失 -> `UNKNOWN`

附加约束：
- 仅当 `trading_days >= 252` 且 `closed_trades >= 20` 时才启用 Sharpe/CAGR 阈值。
- 若发现指标自相矛盾，例如 `trades = 0` 但净值显著变化，则直接 `FAIL`。
- 集中度 v1 只使用 symbol-level 口径，优先读 `perf.top10_profit_concentration`，为空时回退到 `symbol_performance.csv` 计算。

选择理由：
- 高收益不自动等于假，但极端异常需要被统一抬出。
- v1 保持最小实现，不引入月度/年度集中度的额外 schema。

### D12: `validate_data` 在 v1 只作为可选证据引用

最小接入方式：
- 在实验运行入口允许传入一个可选的 `validation_audit_ref`。
- `stabilize_experiment_result()` 如果拿到该 ref，则在 research audit 收尾写盘时写入 `research_audit.evidence_refs.validate_data`。
- 若未提供，则该字段为 `null`，相关 gate 不因此失败。

选择理由：
- 当前 `validate_data` 与实验运行是两条线，强行改成强绑定会扩大改造范围。
- 用户的 v1 目标是统一收口和 verdict，不是重排整个运行前置流程。

### D13: `report_generator` 在 v1 不作为强依赖改造点

v1 默认不要求 [report_generator.py](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/report/report_generator.py) 消费 `research_audit`。

可选增强：
- 仅在报告顶部增加只读“研究审计结论”区块
- 只展示 `overall_status` 与失败 gate

选择理由：
- 报表当前主要消费 `run_meta/perf/trades`，改它不是 v1 主目标。
- 先把审计 contract 固化，再决定是否做展示层补丁。

## Risks / Trade-offs

- [风险] `ALL_A` 被判为 `CURRENT_SNAPSHOT/FAIL` 会让部分历史研究结果立即暴露为不可信
  -> Mitigation：这是研究纪律本身要求暴露的问题，不做静默放宽；如未来修正为逐日 PIT universe，再让 gate 重新晋级。

- [风险] `execution_realism` 需要在 artifact stabilize 阶段追加最小 DB 回查
  -> Mitigation：只回查成交涉及的 symbols/date 范围；若 DB 不可用，则 gate 降级为 `UNKNOWN`，不阻断实验产物落盘。

- [风险] 历史实验目录 schema 混杂，不能简单拿新规则去回判旧实验
  -> Mitigation：v1 只保证新生成实验具备 `research_audit`；历史实验不做回填与 retroactive FAIL。

- [风险] `validate_data` 仍是旁路能力，未提供 request_id 时证据链不完整
  -> Mitigation：明确其在 v1 中是 optional evidence，而不是 required gate input。

- [风险] `result_sanity` 阈值过严可能误伤短样本实验
  -> Mitigation：加入最小样本门槛，并优先用 `WARN` 而不是 `FAIL` 标记极端收益。

## Migration Plan

1. 新增 `backtest-research-audit` change artifacts，固定 contract 与 gate 规则。
2. 在 `backend/core/audit/` 新增 research audit 构建模块，保持 `experiment_audit.py` 继续负责 stage contract。
3. 在 `stabilize_experiment_result()` 的收尾阶段接入 `research_audit` 生成与 `audit.json` 合并写盘，保持 `ensure_standard_artifacts()` 继续只负责基础 artifact 标准化。
4. 允许实验入口可选传入 `validation_audit_ref`，但不改变 `validate_data` 独立 API 的现有行为。
5. 补充定向校验：
   - 新实验目录包含 `audit.json.research_audit`
   - `run_meta/manifest/stage_summary` 不被重复拷贝
   - `overall_status` 聚合符合 contract
   - `ALL_A`、`HS300_ZZ500`、`CUSTOM` 的 `universe_lineage` 落判符合预期
6. 用一个基线实验和一个新实验样本验证产物 schema 与回归稳定性。

回滚策略：
- 若 research audit 影响 `audit.json` 的既有字段或 artifact compare，可先回滚 research subtree 写入，保留现有 execution audit。
- 若 `execution_realism` 的 DB 回查影响稳定性，可临时将该 gate 退回 `UNKNOWN`，不回滚其他 gate。

## Open Questions

- `CUSTOM` 股票池在未来是否需要单独拆出 `USER_STATIC` 模式，而不是长期保留在 `UNKNOWN`。
- `result_sanity` 是否需要在 v2 增加月度/年度收益集中度，而不再只看 symbol-level 集中度。
- `validate_data` 是否要在后续版本升级为实验前置检查，并把 `request_id` 自动绑定到 `exp_id`。
