## Design

### Change Level

本变更是 L3 研究变更，因为它涉及 ETF 池角色、防守层边界、弱状态目标暴露和组合回测结果解释。实施顺序必须是：规格 -> 静态审计 -> 最小研究配置 -> 三窗口回测 -> 审计结论。

### Research Boundary

本轮只研究 `CN_STOCK_ETF_COMBO_BASELINE_V2` 的回撤修正，不讨论收益最大化，也不升级正式 baseline。

固定项：

- stock leg 使用现有组合模板中的 stock component，不改选股、排序、退出、交易和预算规则。
- ETF 选股机制仍使用当前低频趋势/相对强弱框架，不引入个股式 alpha 因子。
- 组合装配仍使用统一 stock+ETF runtime，不改账户层主真相。
- 跨境 ETF 全部排除，后续另案接入。

可研究项：

- 当前 99 ETF 池的国内子集。
- ETF beta 与 defense 角色分类。
- `TRANS_DOWN / RISK_OFF` 下 ETF sleeve 的目标暴露、可部署暴露、防守资产权重和 fallback。
- 行业/主题 ETF 是否应只作为卫星候选，而不是默认 beta 仓。

### ETF Role Model

本轮角色分类先按 catalog / role map 做静态审计：

- `exclude_cross_border`: QDII / 港股 / 美股 / 中概跨境 ETF，全部剔除。
- `defense`: 黄金、国债、久期层、货币 ETF / 现金替代。
- `beta_broad`: 沪深300、上证50、中证500、中证1000、创业板、科创等国内市场 beta。
- `beta_style_smart`: 红利、低波、质量、价值、A500、央企、增强、等权、成长风格。
- `satellite_industry_theme`: 行业/主题 ETF，仅作为卫星研究层，不直接承担防守仓。

### Minimal Experiment Shape

第一轮最小实验不新增核心模块，优先通过 research study variant 表达：

1. `DOMESTIC_POOL_BASE`: 99 ETF 池剔除跨境，其他参数尽量保持 V2。
2. `DOMESTIC_DEFENSE_TIGHT`: 在 `DOMESTIC_POOL_BASE` 上只收紧弱状态 beta 暴露，提高 defense/cash 占比。
3. `DOMESTIC_NO_THEME_WEAK`: 弱状态下禁止行业主题进入 ETF beta，测试回撤是否改善。

每轮只允许一个主改动；若需要组合多个改动，必须作为第二阶段。

### Metrics And Gates

主要验收不是 CAGR，而是：

- `max_drawdown`
- `calmar`
- `weak_state_actual_exposure`
- `weak_state_defense_exposure`
- `weak_state_beta_exposure`
- `ETF leg drawdown contribution`
- `combo vs stock-only / ETF-only attribution`

硬要求：

- 与 V2 对比，`2012-2026` 最大回撤必须改善，且收益不能明显坍塌。
- `2012-2017` 不得出现硬门槛恶化。
- 所有产物必须保留 ETF 分类、跨境剔除清单、弱状态暴露解释。

### Rollback

- 删除本轮 research-only study variant 即可回退。
- 不改变正式 baseline index。
- 不改变正式 ETF pool 和正式 runtime 默认参数。
