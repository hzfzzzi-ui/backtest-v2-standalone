## Context

当前 `stock + ETF` 组合已经完成执行口径侧的关键清理：`PIT`、`NEXT_OPEN`、`price_adj` 与 `accounting` 都已经能在组合审计中给出 `PASS`。当前无法晋升正式主线的唯一阻塞，不在执行实现，而在 ETF sleeve 仍沿用研究态的资产池、入口身份、fallback 语义与输出合同。

当前最新组合候选已经满足收益参考线：`13.30% CAGR / 0.4908 Sharpe / -31.39% MaxDD`。但 `etf_beta_sleeve = FAIL`，说明系统仍把 ETF 组件判定为 `do_not_promote`。如果不先收正式合同，就会继续出现“执行口径已干净，但组合仍不能晋升主线”的治理断层。

本次设计的利益相关方只有两类：
- 主线治理：需要一个可审计、可回退、可复现的正式组合主线合同
- 研究推进：需要保留 ETF 研究态扩池与 explain 能力，但不能污染 formal mainline

## Goals / Non-Goals

**Goals:**
- 将 `stock + ETF` 组合定义为新的正式主线升级目标，而不是研究态组合
- 将 ETF sleeve 收口为 `formal ETF stabilizer`
- 定义 `formal_etf_pool_v1`，明确 Phase 1 in-scope / defense / excluded 范围
- 将 weak-state / fallback 正式边界纳入主线合同
- 剥离 formal output contract 中的 research-only 字段与 reason family
- 将 promotion gate 固定为：审计全 `PASS`，收益不明显差于当前组合候选锚点

**Non-Goals:**
- 本次不扩展 ETF 池到新的研究标的
- 本次不引入新的 ETF alpha/ranking 逻辑
- 本次不重写 stock sleeve 主逻辑
- 本次不处理美股、加密或 defense 新资产接入
- 本次不要求 ETF sleeve 单独收益优于当前研究态版本

## Decisions

### Decision 1：直接以“组合主线升级”为目标，而不是先升 standalone ETF 主线
- 选择：直接把 `stock + ETF` 组合作为 promotion 对象
- 不选：先把 ETF 做成独立 standalone mainline，再回挂组合
- 原因：当前用户目标是组合主线晋升，不是独立 ETF 产品治理；两段式升级只会引入额外口径漂移

### Decision 2：ETF 组件正式身份固定为 `formal ETF stabilizer`
- 选择：formal 组合中的 ETF 组件使用 `formal ETF stabilizer / allocation sleeve` 身份
- 不选：继续沿用 `governed_broad_based_standalone_mainline`
- 原因：当前组合中的 ETF 角色是预算承接与稳态配置，不是独立 broad-based standalone 产品；身份不统一会继续触发 `formal_alignment_status = do_not_promote`

### Decision 3：主线资产池采用“版本化冻结”，而不是“运行时随手扩池”
- 选择：定义 `formal_etf_pool_v1`，后续扩池必须通过 `v2/v3` 显式演进
- 不选：在 formal mainline 下继续让研究标的动态混入
- 原因：formal mainline 需要可复现；冻结的是版本，不是否定未来扩池能力

### Decision 4：weak-state / fallback 作为本次 promotion 的正式合同一部分
- 选择：把 `RISK_OFF / TRANS_DOWN` 的 defense/fallback 资产边界与输出语义一起收口
- 不选：保留为“当前研究下的一个固定逻辑”以后再说
- 原因：一旦进入正式主线，这就是系统在最差状态下的正式行为；不能留在研究态语义里漂移

### Decision 5：formal output contract 与 research diagnostics 分层
- 选择：formal output 只保留正式语义字段；research-only reason family 与 explain 继续留在 diagnostics/internal audit
- 不选：把 research-only 字段继续暴露在 formal 产物中
- 原因：formal 主线必须可解释，但不能把研究诊断当主真相

### Decision 6：promotion gate 以“审计全 PASS + 收益守门”双门槛执行
- 选择：审计必须全 `PASS`；收益不得明显差于当前组合候选锚点 `13.30 / 0.4908 / -31.39%`
- 不选：只看收益或只看审计
- 原因：本项目最高优先级是可信、可审计、稳健，而不是单次收益最大化

## Risks / Trade-offs

- [Risk] formal ETF 池过窄，短期可能压低收益上限 → Mitigation：使用 `formal_etf_pool_v1`，后续若要扩池，显式起 `v2`，而不是在主线内漂移
- [Risk] 剥离 research-only 字段后，前端或审计视图可能缺失部分解释 → Mitigation：保留 internal diagnostics / research audit，不让 formal contract 承担研究噪声
- [Risk] weak-state/fallback 边界收紧后，某些历史研究路径会失效 → Mitigation：明确区分 formal mainline 与 research branch，允许研究分支继续存在但不得冒充主线
- [Risk] promotion 后收益可能小幅回落 → Mitigation：将收益守门线写入任务验收，若明显差于当前组合候选锚点则不晋升

## Migration Plan

1. 先定义 `formal_etf_pool_v1` 与 `formal ETF stabilizer` 身份合同
2. 再修改 ETF sleeve compile input、entry type、boundary mode 与输出合同
3. 单独重跑 ETF sleeve，要求 `etf_beta_sleeve = PASS`
4. 将通过的 ETF sleeve 挂回 unified combo，再重跑组合审计
5. 只有在组合 `overall_status = PASS` 且收益守门通过时，才允许更新正式主线锚点

## Open Questions

- `formal_etf_pool_v1` 中 `511010.SH` 是否作为唯一 formal defense，还是允许未来在 `v2` 中再引入第二个 formal defense 资产
- promotion 完成后，是否同步把当前 `A_STOCK_ETF_V1` 及相关结果展示口径重命名为正式主线命名
