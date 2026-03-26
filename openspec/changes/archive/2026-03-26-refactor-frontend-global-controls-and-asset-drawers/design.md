## Context

当前桌面研究台采用“顶栏 + 左侧 `S1-S9` 阶段抽屉 + 中间结果区 + 状态中心”的布局。这个布局在单一 A 股研究阶段可用，但现在系统已经形成了更明确的分层：

- 顶层公共能力：`market_regime_engine`、`global_portfolio_governor`
- 资产或 sleeve 特化能力：`cn_stock_trend_alpha_core`、`cn_etf_beta`
- 横切解释层：`attribution_audit`

问题不在于页面信息不够，而在于页面职责错位：`Regime` 和 `Governor` 仍被埋在左侧阶段化配置里，导致左侧同时承担全局公共控制和资产特化配置。随着 ETF 入口和 governed snapshot 已经进入前端，继续维持当前布局会放大三类问题：

- 左侧拥挤，用户难以区分“这是全局规则”还是“这是当前资产逻辑”
- ETF 仍被展示成股票研究台的变体，而不是正式的 `cn_etf_beta`
- 中间结果区只能在总览卡里塞入 governed 字段，无法形成正式解释面板

## Goals / Non-Goals

**Goals:**
- 将前端页面正式重排为“顶部全局控制层 + 左侧资产特化抽屉 + 中间结果面板”
- 让 `asset_scope` 切换同时驱动文案、抽屉模块和结果摘要，而不只是切换数据上下文
- 将 `Regime` 与 `Governor` 作为系统公共层显式上移到页面顶部
- 将结果区正式拆成 `Performance / Regime / Governor / Attribution`
- 保持现有运行入口、snapshot 真相和结果渲染链路兼容，不引入前端重算研究逻辑

**Non-Goals:**
- 不在本轮实现新的研究策略或新的运行 contract
- 不在本轮实现完整的 manual override 控制台
- 不在本轮完成旧壳到 Vue workbench 的全面迁移
- 不在本轮引入移动端重排或新的视觉设计系统

## Decisions

### 1. 顶部新增 `Global Control Strip`，承载系统公共层
- 决策：资产范围、时间范围、Regime 和 Governor 统一上移到顶部全局控制层。
- 原因：这四类配置不属于任何单资产或单 sleeve；继续留在左侧会把全局控制误导成资产特化参数。
- 备选方案：
  - 保持 `S1-S9` 并仅调整文案：改动最小，但职责仍混乱。
  - 把全部配置放到顶部：顶部会过厚，且资产特化参数编辑体验差。

### 2. 左侧抽屉按 `asset_scope` 和 sleeve 语义切换
- 决策：左侧不再承担全局控制，只显示当前资产的特化模块。
- 个股模式显示：
  - 股票范围
  - 股票 alpha 参数
  - 左侧蓝筹预留位
- ETF 模式显示：
  - ETF 候选池
  - ETF beta 排序与调仓逻辑
  - 防守/保险预留位
- 原因：用户切换资产范围时，真正应该变化的是左侧特化参数，而不是顶层公共规则。
- 备选方案：
  - 维持统一左侧表单，按控件隐藏显示：技术上简单，但页面语义仍然拥挤，容易继续“股票中心化”。

### 3. 中间结果区保持主区域，但升级为四类正式面板
- 决策：不推翻现有结果工作台，只是在其上正式组织四类结果视图：
  - `Performance`
  - `Regime`
  - `Governor`
  - `Attribution`
- 原因：当前 governed snapshot、reason codes、manual override 摘要已进入结果摘要层，继续把这些信息塞在 Overview 卡片里会让解释层失去结构。
- 备选方案：
  - 把 Regime/Governor 放入左侧配置：会混淆“参数”和“结果”。

### 4. `S1-S9` 退化为兼容映射，而不再作为正式页面主结构
- 决策：保留旧阶段面板与旧壳文件的兼容职责，但主架构不再以 `S1-S9` 为正式页面模型。
- 原因：这批文件仍是过渡层，直接硬删风险高；但继续把它们当正式主架构会阻碍 governed 多 sleeve 的页面表达。

### 5. ETF 模式必须显式表达 `cn_etf_beta`
- 决策：当前前端在 `asset_scope='cn_etf'` 时，左侧和结果区都必须采用 ETF beta 语义，而不是复用“股票池 / 个股排序 / PIT”表达。
- 原因：ETF 已经进入 governed 多 sleeve 主线；如果 UI 仍把 ETF 当股票的旁路变体，会误导配置和结果解释。

## Risks / Trade-offs

- [风险] 旧壳与新布局双轨并存会增加短期复杂度  
  → Mitigation：明确旧壳只做兼容层，新能力优先进入结果工作台和新的顶部/抽屉组织。

- [风险] 顶部全局控制层过厚，影响可用性  
  → Mitigation：顶部仅展示摘要和主要入口，详细编辑仍在展开区域或抽屉内完成。

- [风险] `asset_scope` 切换后左侧表单大量变化，可能影响用户习惯  
  → Mitigation：保留稳定的顶栏与结果区，左侧仅逐步收口为资产特化配置。

- [风险] 结果区拆分面板需要更多 snapshot 规范字段  
  → Mitigation：通过 delta spec 明确面板对 snapshot 的依赖范围，避免前端自行拼装或重算。

- [风险] 本轮仅做布局与职责调整，不一定立即降低旧壳代码复杂度  
  → Mitigation：把“旧壳瘦身 / Vue 全迁移”明确放到后续 change，而不是混入本轮。

## Migration Plan

1. 先在 spec 层锁定“顶部公共层 / 左侧资产特化层 / 中间结果面板”的正式职责边界。
2. 在实现阶段优先打通：
   - 顶部全局控制 strip 的摘要与入口
   - `asset_scope` 驱动的左侧抽屉切换
   - 结果区的 `Regime / Governor / Attribution` 面板
3. 保持旧的 `S1-S9` 和旧壳脚本作为过渡兼容，不在第一轮强拆。
4. 验证通过后，再考虑进一步瘦身旧壳和抽离更明确的 Vue shell。
5. 回退时可以逐层回退：
   - 先回退结果面板拆分
   - 再回退顶部全局控制 strip
   - 最后回退资产特化抽屉切换

## Open Questions

- 顶部全局控制层采用固定四张卡片，还是摘要条 + 弹出编辑器，哪种更符合现有 CSS 与桌面宽度约束。
- `value_bluechip_satellite` 与 `insurance_overlay` 在前端左侧是先作为占位卡，还是完全隐藏到后续 change。
- 历史页和实验对比页是否在本轮一并资产感知化，还是留到后续前端迭代。
