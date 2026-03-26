## Context

当前 A 股 governed 主线已经完成了三件事：

- `baseline_V10.1` 被正式重定位为 `cn_stock_trend_alpha_core`
- `cn_etf_beta` 已经有独立 provider/read path 和最小可交易规则
- 前端已经固定了 `cfg_cn_stock_etf_v1` 作为“个股 alpha + ETF beta”组合锚点

但运行层仍保留单一 `asset_scope` 约束。事实结果是：

- 个股实验只能以 `cn_a_equity` 运行
- ETF 实验只能以 `cn_etf` 运行
- 所谓“股+ETF 组合”只能通过两次实验再手工合成 NAV

这与当前架构文档和前端锚点的语义不一致，也让 Governor 只能在 contract 层表达“多 sleeve”，不能在运行时真正裁决两个 sleeve 的预算与结果汇总。

本次 change 的相关约束：

- 必须继续以 canonical 5-state 作为唯一正式状态真相源
- 必须保持配置唯一真相，不能让前端锚点和后端执行口径分叉
- 必须输出组合级与 sleeve 级最小诊断，不允许只给最终收益
- 不在本轮引入左侧蓝筹、保险层或新的资产域

## Goals / Non-Goals

**Goals:**

- 让 `cfg_cn_stock_etf_v1` 可以触发一次真正的统一运行，而不是研究态拼接
- 在单次实验里同时运行 `cn_stock_trend_alpha_core` 与 `cn_etf_beta`
- 让 `global_portfolio_governor` 在同一运行内对两个 sleeve 同时下发预算并收口组合结果
- 输出组合级、股票 sleeve、ETF sleeve 三层结果与最小审计字段
- 保持前端、run_meta、audit、snapshot 对 unified runtime 的一致解释

**Non-Goals:**

- 不在本轮引入 `value_bluechip_satellite`
- 不在本轮引入 `insurance_overlay`
- 不在本轮扩张 ETF 正式范围到 `518880/511010/588000/159915`
- 不在本轮改变 `baseline_V10.1` 的核心 alpha 逻辑
- 不在本轮把统一运行入口推广到美股或其他资产域

## Decisions

### 1. 统一运行入口以 `governed_a_share` 为真相，而不是继续以全局单一 `asset_scope` 为真相

**决策**：
统一运行实验将以 `governed_a_share` 下的 sleeve 定义作为运行真相，允许：

- 组合级 `system_asset_scope = cn_a_multi_sleeve`
- sleeve 级 `asset_scope = cn_a_equity` / `cn_etf`

**原因**：
当前单一 `asset_scope` 模型天然无法表达“一个组合下两种可交易资产读同一次 Governor 预算”的情况。

**备选方案**：
- 继续用两次实验 + 后处理拼 NAV  
  不采用，因为这会绕开 Governor 真正的预算裁决，也无法形成正式统一产物。
- 把 ETF 强塞进 `cn_a_equity`  
  不采用，因为会污染资产语义和读表逻辑。

### 2. 统一运行采用“组合 orchestrator + sleeve provider”模式，不重写底层股票/ETF provider

**决策**：
新增统一运行 orchestrator，在一次实验中分别调用：

- `cn_stock_trend_alpha_core` 的股票 provider
- `cn_etf_beta` 的 ETF provider

然后在 Governor 和组合汇总层收口。

**原因**：
当前两条 sleeve 都已经有独立可运行链路，复用它们比重写单一超级 provider 更稳。

**备选方案**：
- 直接写一个混合 provider 同时读取股票和 ETF  
  不采用，因为会让 asset-specific 逻辑和 read path 重新耦合。

### 3. Governor 输出先定义为“组合预算 + sleeve 预算 + sleeve 部署状态”三层

**决策**：
Governor 在 unified runtime 中至少输出：

- 组合级：`total_risk_budget`、`total_exposure_cap`
- sleeve 级：`sleeve_budgets`
- 部署级：`deployable_slots`、`deployment_reason_codes`

**原因**：
如果只有组合预算，没有 sleeve 级部署状态，前端和 audit 无法回答“为什么 ETF 没吃满”“为什么股票被压缩”。

### 4. 统一运行产物必须同时保留组合级与 sleeve 级结果

**决策**：
单次 unified runtime 至少输出：

- 组合级 `perf/nav/portfolio_daily`
- 股票 sleeve 级摘要
- ETF sleeve 级摘要
- 统一 `run_meta/audit/snapshot`

必要时允许附带：

- `component_nav.csv`
- `sleeve_budget.csv`
- `sleeve_reason_codes.csv`

**原因**：
只给组合净值会让后续分析无法归因；只给两条 sleeve 又不能称为统一运行。

### 5. 前端锚点 `cfg_cn_stock_etf_v1` 继续保留，但语义从“研究组合模板”升级成“统一运行入口模板”

**决策**：
保留 `cfg_cn_stock_etf_v1` 的配置 ID，不重新造第二个名字；通过编译链升级它的运行语义。

**原因**：
前端已经开始围绕这个锚点使用，换 ID 会让配置入口和用户心智再分叉一次。

## Risks / Trade-offs

- **[风险] 统一运行会让当前单 asset_scope 假设的模块报错或偷偷读错表**  
  → **缓解**：引入组合级 asset context 和 sleeve 级 asset context 双层解析，禁止默认回落到单资产全局表。

- **[风险] Governor 预算 contract 已有，但统一运行里真正部署两个 sleeve 后，预算冲突会暴露**  
  → **缓解**：先把预算输出和 reason codes 做全，再做更激进的部署策略。

- **[风险] 产物协议膨胀，前端 snapshot 过重**  
  → **缓解**：结果工作台只强制吃最小摘要，细粒度 diagnostics 继续走附属 artifact。

- **[风险] 统一运行入口一上来就追求最优配比，会把 change 目标做乱**  
  → **缓解**：本轮只保证“真正统一运行”，不在本轮固定长期配比优化。

## Migration Plan

1. 先扩展前端锚点编译与 runtime config compilation，使 `cfg_cn_stock_etf_v1` 可生成统一运行配置
2. 再引入统一运行 orchestrator，允许单次实验同时拉起股票 sleeve 与 ETF sleeve
3. 再把 Governor、accounting、audit、artifact finalize 改成消费组合级 + sleeve 级结果
4. 再补前端 snapshot 与结果工作台的 unified runtime 展示
5. 最后用 `A股个股+ETFV1` 做最小 smoke run，验证：
   - 单次实验确实同时包含两条 sleeve
   - 组合级产物存在
   - 研究审计通过

回退策略：

- 若统一编译链不稳定，可先回退到旧的单 asset_scope 运行入口
- 若 unified runtime 汇总层不稳定，可保留两条 sleeve 独立运行，不发布统一入口
- 任何回退都不得破坏现有 `baseline_V10.1` 单独运行与 `cn_etf_beta` 单独运行能力

## Open Questions

- Phase 1 是否把组合默认配比固定为 50/50，还是仅支持由 Governor 配置显式指定  
- unified runtime 的组合 benchmark 默认取什么：
  - 继续取股票 benchmark
  - ETF 第一标的
  - 还是单独定义组合 benchmark 语义
- 组合级 trades/orders 是否只保留统一表，还是同时提供组合表和 sleeve 子表
