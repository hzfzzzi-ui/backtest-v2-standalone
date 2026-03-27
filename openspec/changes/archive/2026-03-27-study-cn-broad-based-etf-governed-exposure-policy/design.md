## Context

当前 ETF 研究已经经过三轮收敛：旧 ETF V1 / 稳定器线证明“单纯低暴露 beta sleeve”难以形成有效收益；模板 A 的 A0 胜出版证明“宽基轮动 + 低频 + Top2 + fallback”开始具备继续研究价值；暴露语义研究又证明“粗暴把 target exposure 往上抬”不会自动带来更好的收益风险比。当前真正缺的不是继续换候选池，而是在同一个 Governor 之下，为宽基 ETF sleeve 定义一套不同于个股 alpha 的暴露响应函数。

当前系统已经具备：
- Governor 统一输出 canonical 5-state 与总风险约束
- ETF beta sleeve 的独立 provider、audit 与 run_meta contract
- A0 宽基轮动模板的最小可交易基线

当前系统缺的是：
- 宽基 ETF 作为配置层的正式暴露政策
- 宽基 ETF 在 `LIGHT / TRANS_DOWN` 下的分层承接与 fallback 语义
- 与个股 alpha 区分开的 sleeve-local exposure translation
- 对“目标暴露、实际暴露、分层承接、部署不足”的统一审计证据

## Goals / Non-Goals

**Goals:**
- 在同一个 Governor 之下，正式定义宽基 ETF sleeve 的本地暴露翻译规则。
- 让宽基 ETF 在 `LIGHT` 与受控 `TRANS_DOWN` 状态下具备不同于个股 alpha 的配置层行为。
- 为宽基 ETF 暴露政策建立最小研究 AB，比较不同 `target_exposure / min_deployable_exposure / layering / fallback` 组合。
- 把新增暴露语义完整落到 `run_meta / audit / research study summary` 中，保证可解释与可回归。

**Non-Goals:**
- 不研究行业 ETF 或主题 ETF。
- 不扩宽基 ETF 候选池。
- 不修改个股 alpha 主逻辑。
- 不在本轮直接推进 unified runtime 组合配比。
- 不继续重做旧 ETF V1 / 稳定器 V2 的规则族。

## Decisions

### 决策 1：Governor 继续统一输出环境真相，但宽基 ETF 使用独立暴露翻译
- 选择：
  - 保持 Governor 继续输出统一的 `effective_state_5 / coarse_state / risk_budget / drawdown / cooldown / defense pressure`
  - 在 ETF sleeve 侧新增 `broad_based_exposure_policy`
- 原因：
  - Governor 负责统一环境真相与总风险边界，不能拆散
  - 当前问题不是 Governor 错，而是 ETF 和个股 alpha 共享了过于相似的收缩习惯
- 放弃方案：
  - 让宽基 ETF 脱离 Governor 单独判断环境
  - 直接复用个股 alpha 的风险开关

### 决策 2：本轮只研究宽基 ETF sleeve，不研究行业 ETF
- 选择：
  - 仅允许宽基与宽基风格指数 ETF 进入本轮正式范围
  - 行业 ETF、主题 ETF、窄行业 ETF 一律排除
- 原因：
  - 本轮目标是把宽基 ETF 作为配置层重新定义，不是展开第二条“战术轮动线”
  - 如果混入行业 ETF，会把“配置层暴露语义”和“行业轮动速度”绑在一起，结果无法归因
- 放弃方案：
  - 同时比较宽基和行业 ETF
  - 在本轮把行业 ETF 预留为正式子策略

### 决策 3：宽基 ETF 允许在 `LIGHT / 受控 TRANS_DOWN` 中保留或分层承接 beta
- 选择：
  - `BULL / TRANS_UP` 维持较高目标暴露
  - `LIGHT` 不直接收缩为接近零，而是保留中等配置暴露
  - `TRANS_DOWN` 不默认清零，而是在 Governor 许可下使用低到中低的分层承接带
  - `RISK_OFF` 才回到极低或零暴露
- 原因：
  - 宽基 ETF 的角色是配置层，不是纯战术顺势仓
  - 在环境转弱但未进入极端风险时，宽基 ETF 有理由以更低成本承接 beta
- 放弃方案：
  - 沿用个股 alpha 的“弱状态快速清零”
  - 反向做无限抄底

### 决策 4：暴露政策研究必须拆成 target / deployability / layering / fallback 四层证据
- 选择：
  - 统一输出：
    - `target_exposure`
    - `min_deployable_exposure`
    - `actual_exposure`
    - `actual_fallback_exposure`
    - `layering_band`
    - `under_deploy_reason_codes`
  - 研究结论不只看 `CAGR`，还必须看平均实际暴露、部署不足分布、fallback 使用率
- 原因：
  - 之前的 ETF 研究已经证明，单看收益很容易把“规则问题”和“暴露问题”混在一起
- 放弃方案：
  - 继续只用 perf 指标判断 ETF 暴露政策优劣

### 决策 5：本轮先用 A0 胜出版作为控制组，不引入新的广泛结构重排
- 选择：
  - 用当前 A0 胜出版作为控制组
  - 在其基础上只研究暴露政策，不同时重做候选池、TopN、月频/周频结构
- 原因：
  - 保持单轮一个主变量，避免再次把“池子、节奏、暴露”绑在一起
- 放弃方案：
  - 一次性改候选池、排序和暴露

## Risks / Trade-offs

- [风险] 宽基 ETF 在 `TRANS_DOWN` 允许分层承接，可能把回撤明显拉大  
  → 缓解：本轮强制要求 `RISK_OFF` 仍保持极低或零暴露，并要求研究产物显式报告 `layering_band` 与 drawdown 贡献。

- [风险] 目标暴露抬高后，实际仍部署不足，研究结论可能再次回到“仓位还是不够”  
  → 缓解：把 `target vs actual vs fallback` 分层写入 audit 与 summary，优先回答“为什么没部署到位”。

- [风险] 宽基 ETF 与行业 ETF 边界不清，后续容易被混回同一个 ETF sleeve  
  → 缓解：在 spec 中明确写死本轮仅覆盖宽基 ETF，行业 ETF 不得进入正式范围。

- [风险] 只研究暴露政策，可能无法直接达到用户预期的 `6%~9% CAGR`  
  → 缓解：在 implementation notes 中区分“暴露语义验证”与“收益目标验证”；如果暴露语义成立但收益仍不足，再另开规则族 change。

- [风险] 与个股 alpha 共享同一个 Governor 时，宽基 ETF 的“更慢、更连续”暴露翻译会让下游实现复杂度提高  
  → 缓解：把新逻辑限制在 ETF sleeve 本地 policy builder，不在 Governor 主状态真相层新增第二套状态机。

## Migration Plan

1. 以 A0 胜出版为控制组，新增宽基 ETF governed exposure policy 配置语义。
2. 在 ETF provider 中实现 sleeve-local exposure translation，不修改 Governor 主状态真相。
3. 在 `run_meta / audit / study summary` 中补齐 target/deployability/layering/fallback 证据。
4. 先跑最小 AB 并输出研究结论，再判断是否值得升格为新的 ETF 主研究线。

回退策略：
- 撤回 ETF sleeve 本地 exposure policy 配置与 provider 分支；
- 保留已有 A0 胜出版控制组不变；
- 若 audit / run_meta 新字段影响下游，可保留兼容只读字段或整体回退本轮新增字段。

## Open Questions

- `TRANS_DOWN` 的宽基分层承接是更适合固定暴露带，还是更适合 drawdown band 驱动？
- `LIGHT` 与 `TRANS_DOWN` 的 fallback 是否应该共享同一资产与同一阈值？
- 研究结论如果显示“暴露更合理但收益仍明显低于目标”，下一轮是先改 fallback，还是先改宽基池结构？
