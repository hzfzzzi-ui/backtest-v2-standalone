## Context

当前正式 ETF sleeve 的 Phase 1 资产边界很窄：core beta 主要是 `510300.SH`、`510500.SH`、`510050.SH`、`512100.SH`，limited defense 是 `511010.SH`。现有 catalog 已有第一批 ETF 和 template 候选，但正式运行合同明确要求 out-of-scope ETF 不得被静默升级。

用户提出“ETF 当前池子太少”。这个判断合理，但资产池扩展会直接影响回测口径和系统主行为，属于 L3。正确路径不是把候选直接加入 formal 池，而是先建立一个 research-only shadow 池，跑三窗口审计，再决定是否另开 `formal_etf_pool_v2`。

## Goals / Non-Goals

**Goals:**

- 建立 `cn_etf_research_shadow_pool_v1`，作为可复现、可审计、可回退的 ETF 扩池研究入口。
- 将候选分成明确角色：红利/价值、黄金防守、成长、科创成长、红利低波对照、小盘替代。
- 明确 shadow 池与 `formal_etf_pool_v1` 隔离，任何候选不得因进入 shadow 自动进入正式交易池。
- 让实验产物输出 pool version、symbol role、coverage window、formal eligibility、promotion gate 和 reject reason。
- 以三窗口研究纪律评估候选：`2016-2026` 主开发窗口、`2012-2017` 硬门槛窗口、`2012-2026` 全周期审计窗口。

**Non-Goals:**

- 不修改当前 live baseline。
- 不修改 ETF 信号时点、成交时点、账户层预算、股票 sleeve 或组合构建主逻辑。
- 不把行业/主题 ETF 纳入本轮正式或 shadow 池。
- 不把 `511880.SH`、`511260.SH` 等现金/久期候选混入同一轮，因为它们需要现金等价物与防守层会计语义。
- 不把 `513500.SH`、`513100.SH` 等跨境 ETF 混入同一轮，因为它们涉及 QDII 溢价、汇率和交易日历。

## Decisions

### 决策 1：shadow 池版本化，formal 池不变

新增 `cn_etf_research_shadow_pool_v1`，不修改 `formal_etf_pool_v1`。实现上应优先新增 catalog preset / role metadata / study yaml，而不是改正式 core symbols 或 limited defense constants。

原因：

- `formal_etf_pool_v1` 是当前可复现锚点的一部分，静默修改会破坏 baseline 可回滚性。
- shadow 池可以允许短历史或待验证候选存在，但 formal 池必须只接受已通过门槛的标的。

备选方案：直接扩展 `CN_ETF_BETA_CORE_SYMBOLS`。放弃，因为这会把研究问题变成正式口径漂移。

### 决策 2：v1 只使用本地已支持或已可审计的候选

`cn_etf_research_shadow_pool_v1` 初始候选限定为：

- `510880.SH`：红利/价值标准候选。
- `512890.SH`：红利低波对照候选，用于和 `510880.SH` 比较角色重叠。
- `518880.SH`：黄金防守/多资产分散候选，不直接归类为 core beta。
- `159915.SZ`：创业板成长候选。
- `588000.SH`：科创成长候选，短历史需要单独标注。
- `159845.SZ`：中证1000标准化替代候选，用于和 `512100.SH` 对照，不增加新的小盘风险预算。

暂缓候选：

- `511880.SH`、`511260.SH`：另案研究现金/久期层。
- `513500.SH`、`513100.SH`：另案研究跨境 ETF。
- 行业/主题 ETF：本轮不纳入。

原因：

- 这些 v1 候选覆盖当前正式池缺失的主要解释维度。
- 其他候选需要新增数据、现金层或跨境语义，混在本轮会导致归因失真。

### 决策 3：shadow 实验必须输出候选角色和 promotion gate

研究产物必须能回答：

- 该 ETF 是 formal、shadow 还是 deferred。
- 它在本轮承担什么角色。
- 数据覆盖是否足以进入对应窗口。
- 三窗口结果是否稳定。
- 若不能转正式，原因是历史太短、流动性不足、风险贡献过高、收益改善不稳定、和既有标的重叠，还是会计/交易语义未定义。

原因：

- 只看 CAGR 会把短期强势主题或短历史幸存样本误判为正式资产。
- promotion gate 是后续是否开启 `formal_etf_pool_v2` 的审计依据。

### 决策 4：研究顺序先做 shadow diagnostics，再做组合候选 AB

实施顺序应是：

1. catalog / preset / study smoke，确认研究入口可复现。
2. 单标的与角色组诊断，输出覆盖、流动性、波动、相关性、分红现金事件覆盖和交易可执行性。
3. 在不改变正式池的前提下跑 shadow 组合 AB，比较“正式池 only”与“正式池 + shadow 候选”。
4. 仅当候选通过三窗口与审计门槛，才另开 change 讨论 `formal_etf_pool_v2`。

原因：

- 先确认数据和解释层可靠，再讨论收益改进。
- 将扩池效果和 formal promotion 拆开，避免一次实验绑定多个核心改动。

## Risks / Trade-offs

- [Risk] `588000.SH`、`159845.SZ` 历史较短，无法完整覆盖 `2012-2017` 硬门槛窗口。  
  → Mitigation: 标记为 short-history shadow，仅允许参与 post-listing diagnostics，不得作为 formal promotion 的完整证据。

- [Risk] `518880.SH` 黄金 ETF 可能更适合多资产防守层，而不是 A 股 ETF beta sleeve。  
  → Mitigation: role 标记为 `shadow_defense_gold`，promotion gate 要求单独判断是否转入防守层而不是 core beta。

- [Risk] 红利 ETF 与红利低波 ETF 角色重叠，盲目同时加入会增加同质暴露。  
  → Mitigation: 输出 overlap / winner comparison，默认只允许形成一个红利角色候选。

- [Risk] 扩池后收益提升可能来自短历史或单一风格阶段。  
  → Mitigation: 必须同时报告 `2016-2026`、`2012-2017`、`2012-2026`，并保留不能完整覆盖窗口的 reject reason。

- [Risk] shadow preset 被误用于正式 baseline。  
  → Mitigation: run_meta 和 audit 必须显式标记 `research_only=true`，formal sleeve 默认必须拒绝 shadow pool promotion。

## Migration Plan

- 新增 shadow preset、role metadata、study 和 audit 字段，不迁移已有 baseline。
- 默认配置继续使用 `formal_etf_pool_v1`。
- 验证通过后，仅生成新的 research artifacts；不更新 live baseline。
- 回退方式：删除新增 shadow preset / study / audit 字段和对应测试，正式池与现有 baseline 不需要迁移。

## Open Questions

- `518880.SH` 最终应归入 ETF sleeve 的 limited defense，还是归入未来多资产防守层。
- `510880.SH` 与 `512890.SH` 是否只保留一个红利角色进入下一阶段。
- 若 `159915.SZ` 与 `588000.SH` 提升收益但显著提高回撤，是否允许作为低权重成长 satellite，而不是正式 core beta。
