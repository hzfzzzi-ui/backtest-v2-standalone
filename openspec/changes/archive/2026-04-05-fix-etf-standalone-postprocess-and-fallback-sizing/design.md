## Context

当前 `etf/cn_broad_based_research_mainline_r1` 的真实回测已经证明，standalone mainline 在 `BULL / TRANS_UP / RISK_OFF` 下的 deployability 合同不再是唯一主瓶颈。实跑暴露出的新问题集中在 postprocess 与 fallback sizing：

- partial fallback fill 场景下，零原始目标的 fallback 标的仍可能通过默认 `target_exposure_per_symbol` 获得正 `target_weight`
- standalone inter-rebalance deploy 的 `target_weight` 实际表达的是 delta deploy gap，但 `research_audit` 仍把它和最终目标仓位直接比较
- `orders.csv`、`portfolio_daily.csv`、`audit.json` 因为比较的不是同一层 target 语义，出现了假阳性的 target contract drift

当前代码断点主要在：
- `backend/core/engine_vector/etf_beta/selection.py`
- `backend/core/engine_vector/etf_beta/execution_paths.py`
- `backend/core/stage_pipeline/adapters/order_planning.py`
- `backend/core/audit/research_audit.py`

## Goals / Non-Goals

**Goals:**
- 明确 standalone mainline 下 `final_target_weight` 与 delta `target_weight` 的双字段语义
- 修正 partial fallback fill 与 standalone deploy 的 postprocess/sizing，使 fallback 标的不再错误继承正目标
- 让 `research_audit` 只检测真实的 final target drift，不再把 delta order 当成 drift
- 通过最小测试与实跑重新验证 `BULL / TRANS_UP` 的 gap 解释是否收敛

**Non-Goals:**
- 不再次放宽 `RISK_OFF / TRANS_UP` 的 deployability 合同
- 不改 formal ETF stabilizer / formal Phase 1 主语义
- 不改 stock+ETF combo
- 不改前端工作台

## Decisions

### 1. 用双字段收口 standalone target 语义
决定：
- 对 standalone inter-rebalance deploy，继续保留 `target_weight` 作为 delta deploy gap
- 新增并透传 `final_target_weight` 表达 postprocess 后的最终组合目标仓位

原因：
- 当前 `target_weight` 已被 order sizing 与部分移动端消费面使用，直接改义风险太高
- 增加 `final_target_weight` 能让 audit 与 artifact 对齐，而不破坏现有 delta sizing 主链

备选：
- 直接把 `target_weight` 改成最终目标仓位  
  放弃原因：会污染既有 standalone delta sizing 语义，并可能影响 `order_planning` / `execution_orders`

### 2. partial fallback fill 只允许压缩原始正目标标的
决定：
- 若 selected 集合中仍存在原始正目标权重标的，则 fallback 标的在 postprocess 后的 `final_target_weight` 与 emitted delta `target_weight` 都保持 `0.0`
- 只有 full fallback replacement 才允许 fallback 集合承接 `live_target`

原因：
- 这与现有主 spec 已经一致，也是当前实跑出现 `sh511010` 错误正权重的直接修复点

备选：
- 保持 fallback 按 `target_exposure_per_symbol` 默认分配  
  放弃原因：会继续制造假 drift，也会把 fallback 标的误写成正式目标

### 3. audit 只对比 final target，不对比 delta order
决定：
- `research_audit` 的 drift 检测改为优先比较 `final_target_weight`
- 对 standalone inter-rebalance deploy，delta `target_weight` 只用于解释 deploy gap，不再参与 final target drift 判断

原因：
- 当前 `orders.csv` 的 `target_weight` 是 delta，不是 final；直接比较本身就是错误比较对象

备选：
- 继续沿用现有 drift 检测，只在少量路径上豁免  
  放弃原因：规则会继续脆弱，且无法从 contract 上解释清楚

## Risks / Trade-offs

- [风险] `final_target_weight` 被误读成新的 order sizing 输入  
  → 通过 spec 和实现限制它只服务 audit/artifacts，不改变现有 sizing 主链

- [风险] monthly rebalance / formal redeploy 也被顺手改义  
  → 通过测试锁定“本轮只影响 standalone inter-rebalance deploy”

- [风险] drift 告警数量下降后掩盖真实问题  
  → 要求 audit 继续保留 standalone delta gap 解释，并对真正的 final target mismatch 保持失败

## Migration Plan

1. 先补 spec 和任务，使这次修复正式聚焦在 target contract 与 audit drift
2. 在 `selection.py` / `execution_paths.py` 中补 `final_target_weight` 与 fallback zero-target 逻辑
3. 在 `research_audit.py` 中切换 drift 比较口径
4. 跑 ETF 相关单测
5. 重跑 `etf/cn_broad_based_research_mainline_r1`，用最新 `audit.json` 复核：
   - drift 是否消失或只剩真实 drift
   - `BULL / TRANS_UP` gap 解释是否收敛

回退：
- 回退 `selection.py`、`execution_paths.py`、`research_audit.py`、相关测试和本 change artifact

## Open Questions

- `final_target_weight` 是否还需要进入 `orders.csv` 之外的更上游 contract 字段，目前先按 ETF 私有 meta 处理
- 若实跑后 `actual_exposure` 仍显著低于 approved target，需继续拆“target contract 已对齐”与“真实 underdeployment 仍存在”这两个问题
