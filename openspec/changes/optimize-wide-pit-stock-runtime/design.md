## Context

当前 A1 失败不是研究结果失败，而是运行容量失败。B0 profile 显示 simulation 是主要耗时阶段；A1 被 OOM kill，说明主要风险在内存峰值和 dense precompute，而不是单纯磁盘输出。

## Goals / Non-Goals

**Goals**

- 将宽 PIT 股票池复杂度从近似 `O(F * T * N_union)` 降低到更接近 `O(F_core * sum(A_t) + F_expensive * sum(C_t))`。
- 所有优化默认必须保持口径等价，或明确标注为非正式诊断路径。
- 优化后先通过 B0 parity，再重跑 A1 `1626`。

**Non-Goals**

- 不改变 `HS300_ZZ500_CSI1000` membership 语义。
- 不提高流动性阈值、不使用 `universe_limit` 产出正式结论。
- 不通过静态当前成分股替代 PIT。
- 不为跑通 A1 而改变 alpha/ranking/exit/portfolio 规则。

## Decisions

### Decision 1: PIT interval pushdown 已被否决

最初设想是按 membership interval + warmup 剪裁输入行，减少无效历史参与后续计算。B0 parity 已证明该实现不是等价优化：它会影响持仓后估值价格或指标 warmup 语义。因此正式研究路径关闭该优化，保留审计字段和失败证据。

### Decision 2: top-k 采用等价 partial selection

当最终只需要 top-k 时，使用 `argpartition` 或等价 partial selection。对 top-k 子集再精排，保持输出顺序稳定。

### Decision 3: candidate-first 只后置昂贵计算

先做 PIT active、tradable、ST、停牌、价格、成交额、风险状态、基础 breakout gate；只对必要候选集合执行昂贵评分。若某一评分的 rank 母体原本是全 active universe，则必须保留母体语义，不能偷换成 candidate-only。

### Decision 4: streaming rolling state 分阶段

完整 streaming engine 风险较高。第一阶段可以先引入可验证原型或单因子 rolling state，必须以 B0 parity 为门槛，不能直接替换正式路径。

### Decision 5: active-set sparse scoring 先做 residual-only 安全子集

下一步不再剪裁价格行，而是拆分数据作用域：

- `indicator_scope`：保留指标 warmup 所需历史。
- `entry_eligible_scope`：只决定能不能新开仓，必须服从 PIT membership。
- `valuation_scope`：保留持仓后估值与退出所需价格。

第一阶段只在当前 B0/A1 的 residual-only 安全子集启用 deferred row-rank：保留 residual raw 的全 active-universe 母体，但不提前物化 `residual_strength_score` 和 `final_score` 的全量 `T * N` 矩阵；在 day-signal 阶段对当天 row 做 rank，并只读取候选和持仓列。该路径必须满足：

- `ranking_mode == residual_only`
- `enable_residual_ranking == true`
- 无 sector quality ranking、无 residual refine、无 source-aware residual、无 bull quality veto、无 profit decay residual exit
- B0 parity 通过前不能作为正式默认路径

## Risks / Trade-offs

- [Risk] interval pushdown 少拿 warmup，导致早期信号漂移。  
  缓解：warmup 取所有已知窗口最大值，并在 run_meta 中写出裁剪审计。

- [Risk] partial selection tie-break 与全排序不同。  
  缓解：top-k 子集精排使用原稳定排序 key；B0 orders/perf parity。

- [Risk] candidate-first 改变 rank 母体。  
  缓解：仅后置不影响母体定义的昂贵计算；高风险分支保留原路径。

- [Risk] streaming rolling state 与 pandas rolling 不完全一致。  
  缓解：先加原型测试，不作为 A1 正式运行默认路径，直到 parity 通过。

## Migration / Rollback

- 所有开关默认保持现有路径，或仅在研究 study 明确开启。
- 回退方式：关闭 runtime optimization flags 或删除本 change 的实现代码。
