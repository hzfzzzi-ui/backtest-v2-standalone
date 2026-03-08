## Context

当前公开主链已经稳定为：

`config_json -> compiler -> DataBundle -> foundation shell -> stage pipeline shell -> legacy adapter -> legacy execution kernel`

上一轮 `v2-stage-adapter-decomposition` 已经把 route、candidate flow、holding flow 和 `S7` planning 从
`legacy_adapter.py` 中拆出，并冻结了这些责任不再回流。现在这个文件剩余的主要责任是：

- 开盘成交与现金/仓位/均价更新
- 基于收盘价的 NAV 快照、turnover、gross exposure 和 daily row 组装
- `PortfolioBacktestResult` 的 DataFrame 组装、指标计算和 metrics augment

这些逻辑仍然混在单个 runtime 类里，导致两个问题：

1. accounting 责任和 stage 编排责任仍未分离，后续很难判断改动是在“会计口径”还是“编排壳”。
2. 如果继续往 `legacy_adapter.py` 添加逻辑，这个文件会再次成为新的单体执行壳。

## Goals / Non-Goals

**Goals:**

- 把 `legacy_adapter.py` 中剩余的 accounting-facing 责任继续拆成独立内部模块。
- 保持公开单路径、交易数学、T+1 时序和实验产物名称不变。
- 让后续收敛阶段可以单独处理 accounting、daily snapshot 和 result bridge，而不是再次修改单体 adapter。
- 继续用锁定基线 `exp_20260308_021045840_cde0` 逐步验证结果不漂移。

**Non-Goals:**

- 不重写 execution kernel。
- 不改变 `portfolio_builder.py` 中的交易、成本、metrics 计算口径。
- 不新增第二条公开执行路径。
- 不在本 change 中删除历史 API、artifact compatibility 层或 research-only 代码。

## Decisions

### D1. 按 accounting 职责拆分，而不是按生命周期大重写

本 change 只做三类模块抽分：

- `fill_accounting.py`
  - 负责开盘成交、现金更新、仓位更新、平均成本更新、trade row 组装
- `daily_accounting.py`
  - 负责收盘 NAV 快照、turnover/exposure 计算、top holdings 和 daily row 组装
- `result_bridge.py`
  - 负责把 `daily_rows / trade_rows / candidate_rows` 组装为 DataFrame，并桥接 `_compute_metrics(...)` 与 `metrics augment`

这样每一类都对应稳定的职责边界，能够最小化 diff 并保留现有 runtime 结构。

备选方案：直接把 `LegacyStageAdapterRuntime` 改写成新的 dataclass 状态机。  
未采用原因：这会同时改变状态承载方式、helper 调用方式和 mutation 顺序，基线漂移风险过高。

### D2. 保持 runtime 对象作为共享状态容器

抽出的 helper 继续操作 `LegacyStageAdapterRuntime` 上的既有字段，或只接收最小必要参数后返回结构化结果；
不在这一轮引入新的全局 state model。

这样可以保证：

- 开盘成交顺序不变
- `provider` 上的 side-effect 清理逻辑不变
- `prev_nav / peak_nav / _traded_value_today` 的更新时间点不变

备选方案：为 accounting 单独引入 immutable ledger snapshot。  
未采用原因：需要重写 fill 和 daily prepare 时点，收益不高但风险很大。

### D3. `legacy_adapter.py` 仍保留少量 orchestration 责任

本 change 完成后，`legacy_adapter.py` 仍允许保留：

- `ensure_day(...)` 的主时序组织
- `stage_output(...)` / `plan_orders(...)` 的委托入口
- route/day-control 读取和 provider day signal 拼接

但它不应再直接内嵌 accounting 和 result bridge 细节。

备选方案：继续把 day controls 一并迁出。  
未采用原因：day control 仍然夹杂 route 特例，属于下一轮更靠近 execution kernel 的收敛问题。

### D4. 所有收敛步骤继续服从锁定基线门禁

每个任务组都必须通过：

- 聚焦单测
- `python backend/scripts/baseline_regression_check.py --rerun --write-to-candidate`

允许的非阻塞漂移仍然只有已经接受的 `report.html` diagnostic hash drift。

## Risks / Trade-offs

- [Risk] helper 抽分后 mutation 顺序变化，导致 T+1 成交或 NAV 口径漂移  
  → Mitigation：保持 `ensure_day(...)` 主顺序不变，只搬运实现体，不重排调用点。

- [Risk] accounting helper 接口设计过度抽象，导致后续代码反而更绕  
  → Mitigation：优先使用“窄 helper + 现有 runtime 字段”模式，不提前设计通用框架。

- [Risk] result bridge 抽分后 metrics augment 丢字段或改类型  
  → Mitigation：针对 `PortfolioBacktestResult.metrics` 的关键字段补定向测试，并用锁定基线比较产物。

- [Risk] 继续保留 route/day-control 在 adapter 中，会让文件仍然显得偏大  
  → Mitigation：本 change 的目标是先收敛 accounting 边界；route/day-control 是否继续拆分留给下一条 change。

## Migration Plan

1. 先抽 `fill_accounting.py`，保持开盘成交、trade row 和 provider side-effect 顺序不变。
2. 补 fill accounting 定向测试，验证买卖成交、现金/仓位更新和 trade row 形状。
3. 再抽 `daily_accounting.py`，保持 NAV snapshot、daily row 和 `prev_nav/peak_nav` 更新顺序不变。
4. 再抽 `result_bridge.py`，把结果 DataFrame 和 metrics 组装迁出 `legacy_adapter.py`。
5. 运行聚焦测试和锁定基线复跑，确认核心产物继续 `PASS`。
6. 更新冻结文档，明确 `legacy_adapter.py` 剩余允许持有的责任。

## Open Questions

- `day controls` 是否应在下一轮与 provider diagnostics 一起迁出 `legacy_adapter.py`，还是先冻结不动。
- `result_bridge.py` 后续是否应直接成为 experiment artifact writer 的上游摘要源，而不再只服务 adapter 内部。
